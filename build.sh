#!/bin/bash
set -e  # Exit on error

# Configuration
APP_NAME="Video Thing"
APP_IDENTIFIER="com.yourdomain.videothing"
APP_VERSION="1.0.0"
SCRIPT_NAME="app.py"
ICON_NAME="icon.icns"

# Directory for the app
APP_DIR="./dist/${APP_NAME}.app"
CONTENTS_DIR="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"
FRAMEWORKS_DIR="$CONTENTS_DIR/Frameworks"
TEMP_DIR="./temp_build"

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf "$APP_DIR" "$TEMP_DIR"
mkdir -p "$TEMP_DIR" "$(dirname "$APP_DIR")"

# Create app directory structure
echo "Creating app bundle structure..."
mkdir -p "$MACOS_DIR" "$RESOURCES_DIR" "$FRAMEWORKS_DIR"

# Download ffmpeg and ffprobe for Intel
echo "Downloading ffmpeg and ffprobe..."
curl -L "https://evermeet.cx/ffmpeg/ffmpeg-5.1.2.zip" -o "$TEMP_DIR/ffmpeg.zip"
curl -L "https://evermeet.cx/ffmpeg/ffprobe-5.1.2.zip" -o "$TEMP_DIR/ffprobe.zip"

echo "Extracting ffmpeg and ffprobe..."
unzip -o "$TEMP_DIR/ffmpeg.zip" -d "$TEMP_DIR"
unzip -o "$TEMP_DIR/ffprobe.zip" -d "$TEMP_DIR"

# Copy ffmpeg and ffprobe
cp "$TEMP_DIR/ffmpeg" "$TEMP_DIR/ffprobe" "$RESOURCES_DIR/"
chmod +x "$RESOURCES_DIR/ffmpeg" "$RESOURCES_DIR/ffprobe"

# Copy app resources
echo "Copying application resources..."
cp "$SCRIPT_NAME" "$RESOURCES_DIR/"
if [ -f "$ICON_NAME" ]; then
    cp "$ICON_NAME" "$RESOURCES_DIR/"
fi

# Create improved first-run script that handles architecture compatibility
cat > "$RESOURCES_DIR/first_run.sh" << 'EOF'
#!/bin/bash
# Get absolute path to the script directory
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Log file for debugging
LOG_FILE="/tmp/videothing_first_run.log"
echo "Starting first_run.sh in $DIR" > "$LOG_FILE"

# Check if this is the first run
FIRST_RUN_FLAG="$DIR/.installed"
if [ ! -f "$FIRST_RUN_FLAG" ]; then
    echo "First run - checking dependencies..." | tee -a "$LOG_FILE"
    
    # Check the system architecture
    ARCH=$(uname -m)
    echo "System architecture: $ARCH" | tee -a "$LOG_FILE"
    
    # Create a temporary Python virtual environment for the right architecture
    echo "Creating temporary virtual environment..." | tee -a "$LOG_FILE"
    TEMP_ENV_DIR="$DIR/venv"
    
    # Remove any existing environment
    if [ -d "$TEMP_ENV_DIR" ]; then
        rm -rf "$TEMP_ENV_DIR"
    fi
    
    # Create a fresh environment
    python3 -m venv "$TEMP_ENV_DIR"

    "$TEMP_ENV_DIR/bin/pip" install --upgrade pip
    
    # Install PyQt6 inside this environment
    echo "Installing PyQt6 in virtual environment..." | tee -a "$LOG_FILE"
    "$TEMP_ENV_DIR/bin/pip" install PyQt6 | tee -a "$LOG_FILE"
    
    # Create flag file to indicate we've run the setup
    touch "$FIRST_RUN_FLAG"
fi

# Use the virtual environment if it exists
if [ -d "$DIR/venv" ]; then
    echo "Using virtual environment for Python..." | tee -a "$LOG_FILE"
    PYTHON_EXE="$DIR/venv/bin/python3"
else
    echo "Using system Python..." | tee -a "$LOG_FILE"
    PYTHON_EXE="python3"
fi

# Now run the actual app
echo "Starting the application with $PYTHON_EXE $DIR/app.py" | tee -a "$LOG_FILE"
cd "$DIR"
"$PYTHON_EXE" "$DIR/app.py" 2>&1 | tee -a "$LOG_FILE"
EOF

chmod +x "$RESOURCES_DIR/first_run.sh"

# Update the main launcher to use the first-run script
cat > "$MACOS_DIR/$APP_NAME" << 'EOF'
#!/bin/bash

# Log file for debugging
LOG_FILE="/tmp/videothing_launcher.log"
echo "Starting Video Thing launcher..." > "$LOG_FILE"

# Get absolute path to the executable directory
SELF_PATH=$(cd -P -- "$(dirname -- "$0")" && pwd -P) && SELF_PATH=$SELF_PATH/$(basename -- "$0")
DIR=$(dirname "$SELF_PATH")
echo "Executable path: $SELF_PATH" >> "$LOG_FILE"
echo "Directory: $DIR" >> "$LOG_FILE"

# Get absolute path to Resources
RESOURCES_DIR="$DIR/../Resources"
if [ -d "$RESOURCES_DIR" ]; then
    RESOURCES_DIR=$(cd "$RESOURCES_DIR" 2>/dev/null && pwd)
    echo "Resources directory: $RESOURCES_DIR" >> "$LOG_FILE"
else
    echo "ERROR: Resources directory not found at $RESOURCES_DIR" >> "$LOG_FILE"
    # Try a fallback approach
    RESOURCES_DIR="$(dirname "$DIR")/Resources"
    if [ -d "$RESOURCES_DIR" ]; then
        RESOURCES_DIR=$(cd "$RESOURCES_DIR" 2>/dev/null && pwd)
        echo "Resources directory (fallback): $RESOURCES_DIR" >> "$LOG_FILE"
    else
        echo "ERROR: Resources directory not found at fallback location either" >> "$LOG_FILE"
        exit 1
    fi
fi

# List the contents of the Resources directory
echo "Contents of Resources directory:" >> "$LOG_FILE"
ls -la "$RESOURCES_DIR" >> "$LOG_FILE"

# Executable permissions
echo "Setting executable permissions..." >> "$LOG_FILE"
if [ -f "$RESOURCES_DIR/ffmpeg" ]; then
    chmod +x "$RESOURCES_DIR/ffmpeg"
    echo "Made ffmpeg executable" >> "$LOG_FILE"
fi
if [ -f "$RESOURCES_DIR/ffprobe" ]; then
    chmod +x "$RESOURCES_DIR/ffprobe"
    echo "Made ffprobe executable" >> "$LOG_FILE"
fi
if [ -f "$RESOURCES_DIR/first_run.sh" ]; then
    chmod +x "$RESOURCES_DIR/first_run.sh"
    echo "Made first_run.sh executable" >> "$LOG_FILE"
else
    echo "ERROR: first_run.sh not found in Resources directory" >> "$LOG_FILE"
    exit 1
fi

# Print environment variables for debugging
echo "Environment variables:" >> "$LOG_FILE"
env >> "$LOG_FILE"

# Run the app
echo "Running first_run.sh..." >> "$LOG_FILE"
"$RESOURCES_DIR/first_run.sh" 2>&1 | tee -a "$LOG_FILE"

# If we get here, check if there was an error
if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo "Error occurred while running first_run.sh" >> "$LOG_FILE"
    exit 1
fi

echo "Launcher script completed successfully" >> "$LOG_FILE"
EOF

chmod +x "$MACOS_DIR/$APP_NAME"

# Create Info.plist
echo "Creating Info.plist..."
cat > "$CONTENTS_DIR/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>CFBundleDevelopmentRegion</key>
	<string>English</string>
	<key>CFBundleDisplayName</key>
	<string>$APP_NAME</string>
	<key>CFBundleExecutable</key>
	<string>$APP_NAME</string>
	<key>CFBundleIconFile</key>
	<string>$ICON_NAME</string>
	<key>CFBundleIdentifier</key>
	<string>$APP_IDENTIFIER</string>
	<key>CFBundleInfoDictionaryVersion</key>
	<string>6.0</string>
	<key>CFBundleName</key>
	<string>$APP_NAME</string>
	<key>CFBundlePackageType</key>
	<string>APPL</string>
	<key>CFBundleShortVersionString</key>
	<string>$APP_VERSION</string>
	<key>CFBundleVersion</key>
	<string>$APP_VERSION</string>
	<key>NSHighResolutionCapable</key>
	<true/>
	<key>LSApplicationCategoryType</key>
	<string>public.app-category.utilities</string>
	<key>LSMinimumSystemVersion</key>
	<string>10.14</string>
	<key>NSHumanReadableCopyright</key>
	<string>Copyright © 2025</string>
	<key>LSUIElement</key>
	<false/>
</dict>
</plist>
EOF

# Create README file
cat > "$RESOURCES_DIR/README.txt" << EOF
Video Thing

This application requires Python 3 to be installed on your Mac.
If you don't have Python 3 installed, please download it from:
https://www.python.org/downloads/

When you first launch the app, it will check for and install
any required Python packages using pip.

Requirements:
- Python 3.6 or higher
- pip (which comes with Python)
- Python's venv module (should come with Python)

Troubleshooting:
If the app doesn't start, check the log files at:
/tmp/videothing_launcher.log
/tmp/videothing_first_run.log
EOF

# Clean up temp files
echo "Cleaning up temporary files..."
rm -rf "$TEMP_DIR"

echo "Build complete! App is available at $APP_DIR"
echo "You can run it with: open \"$APP_DIR\""

# Create DMG file for distribution
echo "Creating DMG for distribution..."
DMG_NAME="$APP_NAME.dmg"
DMG_TEMP="temp_$DMG_NAME"
DMG_VOLUME="$APP_NAME"

# Remove existing DMG files if they exist
if [ -f "$DMG_NAME" ]; then
    echo "Removing existing DMG file..."
    rm -f "$DMG_NAME"
fi

if [ -f "$DMG_TEMP" ]; then
    echo "Removing existing temporary DMG file..."
    rm -f "$DMG_TEMP"
fi

# Create a DMG directly from the app folder
hdiutil create -volname "$DMG_VOLUME" -srcfolder "$APP_DIR" -ov -format UDZO "$DMG_NAME"

echo "DMG created: $DMG_NAME"
echo "Distribution complete!"
