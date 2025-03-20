#!/usr/bin/python3

import re
import sys
import subprocess
import os
import tempfile
import urllib.request
import shutil
#import pkg_resources
import multiprocessing

# Now import PyQt classes
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                           QPushButton, QMessageBox, QListWidget,
                           QHBoxLayout, QProgressBar, QLabel, QFileDialog,
                           QMenuBar, QMenu, QStatusBar)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction

class MergeWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)

    def __init__(self, video_paths, audio_paths, output_path):
        super().__init__()
        self.video_paths = video_paths
        self.audio_paths = audio_paths
        self.output_path = output_path
        self.is_cancelled = False
        self.caffeinate_process = None

    def run(self):
        try:
            # Start caffeinate to prevent sleep (macOS only)
            if sys.platform == 'darwin':
                self.caffeinate_process = subprocess.Popen(
                    ['caffeinate', '-i', '-m', '-s', '-d'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                if debug:
                    print("Started caffeinate process to prevent sleep")

            self.progress.emit(1)
            if self.is_cancelled:
                return

            # Step 1: Merge audio files
            merged_audio = self.get_temp_path("merged_audio.mp3")
            self.merge_audio_files(merged_audio)
            self.progress.emit(5)

            if self.is_cancelled:
                return

            # Step 2: Create final video
            self.create_final_video(merged_audio)

            self.finished.emit(True, self.output_path)

        except Exception as e:
            self.finished.emit(False, str(e))
        finally:
            # Cleanup
            if os.path.exists(merged_audio):
                os.remove(merged_audio)

            # Stop caffeinate process to allow system to sleep again
            if self.caffeinate_process:
                self.caffeinate_process.terminate()
                if debug:
                    print("Terminated caffeinate process")

    def get_binary_path(self, binary_name):
        """Find the path to a bundled binary (ffmpeg or ffprobe)."""
        # py2app specific - check if running as a bundled .app
        if hasattr(sys, "frozen") and sys.frozen:
            # Get the Resources directory in the app bundle
            if getattr(sys, 'frozen', False) and getattr(sys, '_MEIPASS', False):
                # PyInstaller case (fallback)
                base_path = sys._MEIPASS
            else:
                # py2app case - use the resource path of the .app bundle
                base_path = os.path.join(os.path.dirname(os.path.dirname(sys.executable)), 'Resources')

            # Return the full path to the binary
            binary_path = os.path.join(base_path, binary_name)
            if os.path.exists(binary_path):
                return binary_path

        # Fallback - look for the binary in the current directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        binary_path = os.path.join(current_dir, binary_name)
        if os.path.exists(binary_path):
            return binary_path

        # Final fallback - assume it's in the PATH
        return binary_name

    def get_temp_path(self, relative_path=''):
        temp_dir = tempfile.gettempdir()
        return os.path.join(temp_dir, relative_path)

    def merge_audio_files(self, output_audio):
        files_path = self.get_temp_path('files.txt')
        with open(files_path, "w") as f:
            for audio_path in self.audio_paths:
                f.write(f"file '{audio_path}'\n")

        # Get the path to the embedded ffmpeg binary
        ffmpeg_path = self.get_binary_path("ffmpeg")

        # Make sure ffmpeg is executable (if it's a file that we can access)
        if os.path.isfile(ffmpeg_path):
            try:
                os.chmod(ffmpeg_path, 0o755)
            except OSError:
                # If we can't chmod, it's probably already executable or we don't have permission
                pass

        cmd = [
            ffmpeg_path,
            "-f", "concat",
            "-safe", "0",
            "-i", files_path,
            "-c", "copy",
            "-y",
            output_audio
        ]

        if debug:
            print(' '.join(cmd))

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        for line in process.stderr:
            if self.is_cancelled:
                process.terminate()
                return

        process.wait()
        os.remove(files_path)

    def create_final_video(self, merged_audio):
        # Get CPU count safely (multiprocessing might not be available)
        try:
            num_cores = multiprocessing.cpu_count()
            num_threads = max(2, num_cores - 1)  # Use all cores except one
        except:
            num_threads = 2  # Fallback to a reasonable default

        # Get the path to the embedded ffmpeg binary
        ffmpeg_path = self.get_binary_path("ffmpeg")

        # Make sure ffmpeg is executable (if it's a file that we can access)
        if os.path.isfile(ffmpeg_path):
            try:
                os.chmod(ffmpeg_path, 0o755)
            except OSError:
                # If we can't chmod, it's probably already executable or we don't have permission
                pass

        cmd = [
            ffmpeg_path,
            "-stats",
            "-i", self.video_paths[0],  # Intro video (plays once)
            "-stream_loop", "-1",
            "-i", self.video_paths[1] if len(self.video_paths) > 1 else self.video_paths[0],  # Main body or repeat intro
            "-i", merged_audio,
            "-filter_complex",
            "[0:v]scale=-1:720[v0];[1:v]scale=-1:720[v1];[v0][v1]concat=n=2:v=1:a=0[v]",
            "-map", "[v]",
            "-map", "2:a",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-shortest",
            #"-threads", str(num_threads),
            "-y",
            self.output_path
        ]

        if debug:
            print(' '.join(cmd))

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        duration = self.get_video_duration(merged_audio)

        for line in process.stderr:
            if self.is_cancelled:
                process.terminate()
                return

            if debug:
                print(line)

            if "time=" in line:
                time = line.split("time=")[1].split()[0]

                if debug:
                    print(time)

                # Try to handle different time formats
                time_parts = time.split(':')
                if len(time_parts) == 3:
                    hours, minutes, seconds = time_parts
                    current_time = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                    progress = int((current_time / duration) * 95) + 5
                    self.progress.emit(progress)

        process.wait()

    def get_video_duration(self, video_path):
        ffprobe_path = self.get_binary_path("ffprobe")
        if os.path.isfile(ffprobe_path):
            try:
                os.chmod(ffprobe_path, 0o755)
            except OSError:
                # If we can't chmod, it's probably already executable or we don't have permission
                pass

        cmd = [
            ffprobe_path,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]

        if debug:
            print(' '.join(cmd))

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

        try:
            duration = float(result.stdout.strip())
            if duration <= 0:
                raise ValueError("Invalid duration")
            return duration
        except (ValueError, TypeError):
            print(f"Error getting duration. ffprobe output: {result.stdout}")
            print(f"ffprobe error: {result.stderr}")
            raise RuntimeError("Failed to get video duration")

    def cancel(self):
        self.is_cancelled = True
        # Make sure to terminate caffeinate process when cancelling
        if self.caffeinate_process:
            self.caffeinate_process.terminate()
            if debug:
                print("Terminated caffeinate process due to cancellation")

class FileDropZone(QWidget):
    def __init__(self, file_type):
        super().__init__()
        self.should_sort = True
        self.file_type = file_type.lower()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.list_widget = QListWidget()
        self.list_widget.setAcceptDrops(True)
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: 2px dashed #666;
                border-radius: 5px;
                padding: 5px;
                background: palette(base);
                color: palette(text);
            }
        """)
        self.list_widget.setMinimumHeight(100)
        self.list_widget.mousePressEvent = self.list_widget_clicked
        self.layout.addWidget(self.list_widget)

        button_layout = QHBoxLayout()
        self.move_up_button = QPushButton("Move Up")
        self.move_down_button = QPushButton("Move Down")
        self.sort_button = QPushButton("Sort")
        self.remove_button = QPushButton("Remove")

        button_style = """
            QPushButton {
                background-color: palette(button);
                color: palette(buttonText);
                padding: 5px;
                border: 1px solid palette(mid);
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: palette(light);
            }
        """
        self.move_up_button.setStyleSheet(button_style)
        self.move_down_button.setStyleSheet(button_style)
        self.sort_button.setStyleSheet(button_style)
        self.remove_button.setStyleSheet(button_style)

        self.move_up_button.clicked.connect(self.move_item_up)
        self.move_down_button.clicked.connect(self.move_item_down)
        self.sort_button.clicked.connect(self.sort_items)
        self.remove_button.clicked.connect(self.remove_selected)

        button_layout.addWidget(self.move_up_button)
        button_layout.addWidget(self.move_down_button)
        button_layout.addWidget(self.sort_button)
        button_layout.addWidget(self.remove_button)
        self.layout.addLayout(button_layout)

        self.filepaths = []
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        # Check if there are any valid files in the drag operation
        if event.mimeData().hasUrls():
            valid_files = any(u.toLocalFile().lower().endswith(f'.{self.file_type}')
                              for u in event.mimeData().urls())
            if valid_files:
                event.acceptProposedAction()
                return

        event.ignore()

    def dropEvent(self, event):
        # Always accept the event first to prevent the bounce-back animation
        event.accept()

        # Then process the files
        files = [u.toLocalFile() for u in event.mimeData().urls()
            if u.toLocalFile().lower().endswith(f'.{self.file_type}')]

        for file in files:
            if file not in self.filepaths:
                self.filepaths.append(file)
                self.list_widget.addItem(os.path.basename(file))

        # Call sort_items after adding new files
        if self.should_sort:
            self.sort_items()

    def list_widget_clicked(self, event):
        if self.list_widget.count() == 0:
            self.browse_files()
        super(QListWidget, self.list_widget).mousePressEvent(event)

    def browse_files(self):
        file_dialog = QFileDialog()
        # Get user's Desktop directory
        documents_dir = os.path.expanduser("~/Desktop")
        files, _ = file_dialog.getOpenFileNames(self, f"Select {self.file_type.upper()} Files", documents_dir, f"{self.file_type.upper()} Files (*.{self.file_type})")
        for file in files:
            if file not in self.filepaths:
                self.filepaths.append(file)
                self.list_widget.addItem(os.path.basename(file))

    def move_item_up(self):
        current_row = self.list_widget.currentRow()
        if current_row > 0:
            self.should_sort = False
            item = self.list_widget.takeItem(current_row)
            self.list_widget.insertItem(current_row - 1, item)
            self.list_widget.setCurrentRow(current_row - 1)
            self.filepaths[current_row], self.filepaths[current_row - 1] = \
                self.filepaths[current_row - 1], self.filepaths[current_row]

    def move_item_down(self):
        current_row = self.list_widget.currentRow()
        if current_row < self.list_widget.count() - 1:
            self.should_sort = False
            item = self.list_widget.takeItem(current_row)
            self.list_widget.insertItem(current_row + 1, item)
            self.list_widget.setCurrentRow(current_row + 1)
            self.filepaths[current_row], self.filepaths[current_row + 1] = \
                self.filepaths[current_row + 1], self.filepaths[current_row]

    def remove_selected(self):
        current_row = self.list_widget.currentRow()
        if current_row >= 0:
            self.list_widget.takeItem(current_row)
            self.filepaths.pop(current_row)

    def sort_items(self):
        def natural_sort_key(s):
            lower_s = s.lower()
            if lower_s == "opening.mp3":
                return (0, )  # Ensures it's always first
            elif lower_s == "closing.mp3":
                return (float('inf'), )  # Ensures it's always last

            # For other files, use natural sorting
            return tuple(
                (1, ) +  # Normal files come after "Opening.mp3" but before "Closing.mp3"
                tuple(
                    "".join((
                        "0" * (8 - len(c)),  # Zero-pad numbers to 8 digits
                        c if c.isdigit() else c.lower()
                    )) for c in re.split(r'(\d+)', s)
                )
            )

        # Sort the filepaths using the custom key function
        self.filepaths.sort(key=lambda x: natural_sort_key(os.path.basename(x)))

        # Clear and repopulate the list widget
        self.list_widget.clear()
        for filepath in self.filepaths:
            self.list_widget.addItem(os.path.basename(filepath))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Super Audio Book Maker 3000 Premium Limited Edition")
        self.setMinimumSize(500, 400)

        # Create menu bar
        self.create_menu_bar()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        video_label = QLabel("Video files...")
        video_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(video_label)

        self.video_zone = FileDropZone("mp4")
        layout.addWidget(self.video_zone)

        audio_label = QLabel("Audio files...")
        audio_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(audio_label)

        self.audio_zone = FileDropZone("mp3")
        layout.addWidget(self.audio_zone)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid palette(mid);
                border-radius: 3px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
            }
        """)

        self.merge_button = QPushButton("Make Video")
        self.set_button_style(is_abort=False)
        self.merge_button.clicked.connect(self.handle_merge_button)

        layout.addWidget(self.progress_bar)
        layout.addWidget(self.merge_button)

        self.merge_worker = None

    def create_menu_bar(self):
        # Create the main menu bar
        menu_bar = self.menuBar()

        # Create the application menu manually
        # On macOS, this will merge with the application menu
        app_menu = menu_bar.addMenu("Video Thing")

        # Add "Check for Updates" action
        update_action = QAction("Check for Updates", self)
        update_action.triggered.connect(self.check_for_updates)
        app_menu.addAction(update_action)

    def check_for_updates(self):
        """Check for updates and update the application in-place by writing to sys.argv[0]."""

        # Get the target path from sys.argv[0]
        target_path = os.path.abspath(sys.argv[0])

        try:
            update_url = "https://raw.githubusercontent.com/corecoding/Video-Thing/refs/heads/main/app.py"

            # Set the app_script_path to sys.argv[0]
            app_script_path = target_path

            # Check if the target file exists and is writable
            if not os.path.exists(app_script_path):
                QMessageBox.critical(self, "Update Error", f"The target file does not exist: {app_script_path}")
                return

            if not os.access(app_script_path, os.W_OK):
                # Try to make it writable
                try:
                    os.chmod(app_script_path, 0o755)
                except Exception as e:
                    QMessageBox.critical(self, "Update Error",
                        f"The target file is not writable: {app_script_path}\nError: {str(e)}")
                    return

            # Create a backup before updating
            backup_path = app_script_path + ".backup"
            try:
                shutil.copy2(app_script_path, backup_path)
            except Exception as e:
                QMessageBox.critical(self, "Update Error",
                    f"Cannot create backup: {str(e)}")
                return

            # Download and compare with current version
            try:
                # Create a request with no-cache headers to prevent GitHub from serving cached content
                req = urllib.request.Request(update_url)
                req.add_header('Pragma', 'no-cache')
                req.add_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                req.add_header('Expires', '0')

                with urllib.request.urlopen(req) as response:
                    latest_version = response.read()

                    with open(app_script_path, 'rb') as current_file:
                        current_version = current_file.read()

                    # Only update if versions are different
                    if latest_version != current_version:
                        # Create a temporary file first, then move it to replace the original
                        temp_file = app_script_path + ".tmp"
                        with open(temp_file, 'wb') as out_file:
                            out_file.write(latest_version)

                        # On Windows, we need to remove the target file first
                        if sys.platform == 'win32' and os.path.exists(app_script_path):
                            os.remove(app_script_path)

                        # Replace the original file with the update
                        shutil.move(temp_file, app_script_path)

                        # On Unix systems, make sure the file is executable
                        if sys.platform != 'win32':
                            os.chmod(app_script_path, 0o755)

                        # Show success message
                        QMessageBox.information(self, "Update Successful",
                            "The application has been updated successfully.\n"
                            "Please restart the application to apply the changes.")

                        # Clean up the backup
                        if os.path.exists(backup_path):
                            try:
                                os.remove(backup_path)
                            except:
                                pass  # Not critical if cleanup fails
                    else:
                        # Versions are the same
                        QMessageBox.information(self, "No Updates", "You already have the latest version.")

                        # Clean up the backup
                        if os.path.exists(backup_path):
                            try:
                                os.remove(backup_path)
                            except:
                                pass  # Not critical if cleanup fails

            except Exception as e:
                # Restore from backup if update failed
                if os.path.exists(backup_path):
                    try:
                        # On Windows, we need to remove the target file first
                        if sys.platform == 'win32' and os.path.exists(app_script_path):
                            os.remove(app_script_path)

                        # Restore from backup
                        shutil.copy2(backup_path, app_script_path)

                        # On Unix systems, restore executable permissions
                        if sys.platform != 'win32':
                            os.chmod(app_script_path, 0o755)

                        # Clean up the backup
                        os.remove(backup_path)
                    except:
                        pass  # Don't add more errors if restore fails

                # Show error message
                QMessageBox.critical(self, "Update Failed",
                    f"Failed to update the application.\nError: {str(e)}")

        except Exception as e:
            # Catch any unexpected errors in the main update logic
            QMessageBox.critical(self, "Update Check Failed",
                f"An unexpected error occurred while checking for updates:\n{str(e)}")

    def set_button_style(self, is_abort):
        if is_abort:
            background_color = "#FF0000"  # Red
            hover_color = "#CC0000"  # Darker red
        else:
            background_color = "#4CAF50"  # Green
            hover_color = "#45a049"  # Darker green

        self.merge_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {background_color};
                color: white;
                padding: 10px;
                font-size: 16px;
                border-radius: 5px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:disabled {{
                background-color: #cccccc;
                color: #666666;
            }}
        """)

    def handle_merge_button(self):
        if self.merge_worker and self.merge_worker.isRunning():
            # Cancel the operation
            self.merge_worker.cancel()
            self.merge_worker.quit()
            self.merge_worker.wait()
            self.merge_button.setText("Make Video")
            self.set_button_style(is_abort=False)
            self.progress_bar.setVisible(False)
        else:
            # Start a new merge operation
            if not self.video_zone.filepaths or not self.audio_zone.filepaths:
                QMessageBox.warning(self, "Error", "Please add both video and audio files.")
                return

            # Open file dialog to select output destination
            documents_dir = os.path.expanduser("~/Desktop")
            default_file = os.path.join(documents_dir, "youtube.mp4")
            output_path, _ = QFileDialog.getSaveFileName(self, "Save Video As", default_file, "MP4 Files (*.mp4)")
            if not output_path:
                return  # User cancelled the file dialog

            # Check if the destination is writable
            if not self.is_path_writable(output_path):
                QMessageBox.critical(self, "Error", f"Cannot write to the selected destination: {output_path}\nPlease choose a different location.")
                return

            self.merge_button.setText("Abort")
            self.set_button_style(is_abort=True)
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)

            self.merge_worker = MergeWorker(self.video_zone.filepaths, self.audio_zone.filepaths, output_path)
            self.merge_worker.progress.connect(self.update_progress)
            self.merge_worker.finished.connect(self.handle_merge_finished)
            self.merge_worker.start()

    def is_path_writable(self, path):
        # Check if the directory is writable
        directory = os.path.dirname(path)
        if not os.access(directory, os.W_OK):
            return False

        # If the file already exists, check if it's writable
        if os.path.exists(path):
            return os.access(path, os.W_OK)

        # If the file doesn't exist, try creating a temporary file
        try:
            testfile = tempfile.NamedTemporaryFile(dir=directory, delete=True)
            testfile.close()
            return True
        except (OSError, IOError):
            return False

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def handle_merge_finished(self, success, message):
        self.merge_button.setText("Make Video")
        self.set_button_style(is_abort=False)
        self.progress_bar.setVisible(False)

        if success:
            QMessageBox.information(self, "Success", f"Video created successfully!\nSaved as: {message}")
        else:
            QMessageBox.critical(self, "Error", f"An error occurred: {message}")

if __name__ == '__main__':
    debug = False

    # Special handling for macOS to change the menu bar app name
    #if sys.platform == 'darwin':
        # This is the crucial line that changes "Python" to "Video Thing" in the menu bar
        # Must be set before creating the QApplication
    #    os.environ['QT_MAC_APP_NAME'] = "Video Thing"

    # Initialize the application
    app = QApplication(sys.argv)

    # Set all the app identification strings to "Video Thing"
    #QCoreApplication.setApplicationName("Video Thing")
    #QCoreApplication.setOrganizationName("Video Thing")
    #app.setApplicationName("Video Thing")
    #app.setOrganizationName("Video Thing")

    # When bundling with py2app, add this to Info.plist:
    # <key>CFBundleName</key>
    # <string>Video Thing</string>

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
