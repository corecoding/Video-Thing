#!/usr/bin/python3

import re
import sys
import subprocess
import os
import pkg_resources
import multiprocessing

required_packages = {
    'PyQt6': 'PyQt6',
}

def install_missing_packages():
    installed_packages = {pkg.key for pkg in pkg_resources.working_set}
    missing_packages = [pkg for pkg_key, pkg in required_packages.items()
                        if pkg_key not in installed_packages]

    if missing_packages:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', *missing_packages])

install_missing_packages()

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QPushButton, QMessageBox, QListWidget,
                             QHBoxLayout, QProgressBar, QLabel, QFileDialog)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

class MergeWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)

    def __init__(self, video_paths, audio_paths, output_path):
        super().__init__()
        self.video_paths = video_paths
        self.audio_paths = audio_paths
        self.output_path = output_path
        self.is_cancelled = False

    def run(self):
        try:
            self.progress.emit(2)
            if self.is_cancelled:
                return

            # Step 1: Merge audio files
            merged_audio = "merged_audio.mp3"
            self.merge_audio_files(merged_audio)
            self.progress.emit(10)

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

    def merge_audio_files(self, output_audio):
        with open("files.txt", "w") as f:
            for audio_path in self.audio_paths:
                f.write(f"file '{audio_path}'\n")

        cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", "files.txt",
            "-c", "copy",
            "-y",
            output_audio
        ]

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        for line in process.stderr:
            if self.is_cancelled:
                process.terminate()
                return
            # Update progress (you might need to adjust this based on FFmpeg output)
            self.progress.emit(10)  # Placeholder progress update

        process.wait()
        os.remove("files.txt")

    def create_final_video(self, merged_audio):
        num_cores = multiprocessing.cpu_count()
        num_threads = max(2, num_cores - 1)  # Use all cores except one

        cmd = [
            "ffmpeg",
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

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        duration = self.get_video_duration(merged_audio)

        for line in process.stderr:
            if self.is_cancelled:
                process.terminate()
                return
            if "time=" in line:
                time = line.split("time=")[1].split()[0]
                hours, minutes, seconds = time.split(':')
                current_time = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                progress = int((current_time / duration) * 90) + 10  # Scale from 10% to 100%
                self.progress.emit(progress)

        process.wait()

    def get_video_duration(self, video_path):
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        return float(result.stdout)

    def cancel(self):
        self.is_cancelled = True

class FileDropZone(QWidget):
    def __init__(self, file_type):
        super().__init__()
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
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()
                if u.toLocalFile().lower().endswith(f'.{self.file_type}')]
        for file in files:
            if file not in self.filepaths:
                self.filepaths.append(file)
                self.list_widget.addItem(os.path.basename(file))

        # Call sort_items after adding new files
        self.sort_items()

    def list_widget_clicked(self, event):
        if self.list_widget.count() == 0:
            self.browse_files()
        super(QListWidget, self.list_widget).mousePressEvent(event)

    def browse_files(self):
        file_dialog = QFileDialog()
        files, _ = file_dialog.getOpenFileNames(self, f"Select {self.file_type.upper()} Files", "", f"{self.file_type.upper()} Files (*.{self.file_type})")
        for file in files:
            if file not in self.filepaths:
                self.filepaths.append(file)
                self.list_widget.addItem(os.path.basename(file))

    def move_item_up(self):
        current_row = self.list_widget.currentRow()
        if current_row > 0:
            item = self.list_widget.takeItem(current_row)
            self.list_widget.insertItem(current_row - 1, item)
            self.list_widget.setCurrentRow(current_row - 1)
            self.filepaths[current_row], self.filepaths[current_row - 1] = \
                self.filepaths[current_row - 1], self.filepaths[current_row]

    def move_item_down(self):
        current_row = self.list_widget.currentRow()
        if current_row < self.list_widget.count() - 1:
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
            output_path, _ = QFileDialog.getSaveFileName(self, "Save Video As", "youtube.mp4", "MP4 Files (*.mp4)")
            if not output_path:
                return  # User cancelled the file dialog

            self.merge_button.setText("Abort")
            self.set_button_style(is_abort=True)
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)

            self.merge_worker = MergeWorker(self.video_zone.filepaths, self.audio_zone.filepaths, output_path)
            self.merge_worker.progress.connect(self.update_progress)
            self.merge_worker.finished.connect(self.handle_merge_finished)
            self.merge_worker.start()

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
    app = QApplication(sys.argv)
    app.setApplicationName("Super ")  # Set the application name
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
