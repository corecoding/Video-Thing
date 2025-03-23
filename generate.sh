#!/bin/bash
set -e  # Exit on error

# Configuration
APP_NAME="Video Thing"
APP_IDENTIFIER="com.yourdomain.videothing"
ICON_NAME="icon.icns"

# Directory for the app
APP_DIR="./template"
CONTENTS_DIR="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"

# main launcher that handles architecture compatibility
echo "Creating $MACOS_DIR/$APP_NAME..."
cat > "$MACOS_DIR/$APP_NAME" << 'EOF'
#!/bin/bash

# Get absolute path to the executable directory
SELF_PATH=$(cd -P -- "$(dirname -- "$0")" && pwd -P) && SELF_PATH=$SELF_PATH/$(basename -- "$0")
DIR=$(dirname "$SELF_PATH")

# Get absolute path to Resources
RESOURCES_DIR="$DIR/../Resources"
if [ -d "$RESOURCES_DIR" ]; then
    RESOURCES_DIR=$(cd "$RESOURCES_DIR" 2>/dev/null && pwd)
else
    # Try a fallback approach
    RESOURCES_DIR="$(dirname "$DIR")/Resources"
    if [ -d "$RESOURCES_DIR" ]; then
        RESOURCES_DIR=$(cd "$RESOURCES_DIR" 2>/dev/null && pwd)
    else
        echo "ERROR: Resources directory not found"
        exit 1
    fi
fi

# Download ffmpeg if not present (for current architecture)
if [ ! -f "$RESOURCES_DIR/ffmpeg" ]; then
  echo "Downloading ffmpeg..."
  curl -JL -o "$RESOURCES_DIR/ffmpeg.zip" https://evermeet.cx/ffmpeg/getrelease/zip
  unzip "$RESOURCES_DIR/ffmpeg.zip" -d "$RESOURCES_DIR"
  rm "$RESOURCES_DIR/ffmpeg.zip"
  chmod +x "$RESOURCES_DIR/ffmpeg"
fi

# Download ffprobe if not present (for current architecture)
if [ ! -f "$RESOURCES_DIR/ffprobe" ]; then
  echo "Downloading ffprobe..."
  curl -JL -o "/tmp/ffprobe.zip" https://evermeet.cx/ffmpeg/getrelease/ffprobe/zip
  unzip "/tmp/ffprobe.zip" -d "$RESOURCES_DIR"
  rm "/tmp/ffprobe.zip"
  chmod +x "$RESOURCES_DIR/ffprobe"
fi

# Check if this is the first run
FIRST_RUN_FLAG="$DIR/.installed"
if [ ! -f "$FIRST_RUN_FLAG" ]; then
    # Create a temporary Python virtual environment for the right architecture
    TEMP_ENV_DIR="$DIR/venv"

    # Remove any existing environment
    if [ -d "$TEMP_ENV_DIR" ]; then
        rm -rf "$TEMP_ENV_DIR"
    fi

    # Create a fresh environment
    python3 -m venv "$TEMP_ENV_DIR"

    "$TEMP_ENV_DIR/bin/pip" install --upgrade pip

    # Install required packages
    "$TEMP_ENV_DIR/bin/pip" install PyQt6 setuptools

    # Create flag file to indicate we've run the setup
    touch "$FIRST_RUN_FLAG"
fi

# Use the virtual environment if it exists
if [ -d "$DIR/venv" ]; then
    PYTHON_EXE="$DIR/venv/bin/python3"
else
    PYTHON_EXE="python3"
fi

#curl -H 'Pragma: no-cache' -z "$RESOURCES_DIR/app.py" -o "$RESOURCES_DIR/app.py" https://raw.githubusercontent.com/corecoding/Video-Thing/refs/heads/main/app.py

# Run the app
cd "$DIR"
"$PYTHON_EXE" "$RESOURCES_DIR/app.py"
EOF

chmod +x "$MACOS_DIR/$APP_NAME"

# Create Info.plist
echo "Creating $CONTENTS_DIR/Info.plist..."
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
    <string>_APP_VERSION_</string>
    <key>CFBundleVersion</key>
    <string>_APP_VERSION_</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSApplicationCategoryType</key>
    <string>public.app-category.utilities</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.14</string>
    <key>NSHumanReadableCopyright</key>
    <string>Copyright © 2025 Core Coding</string>
    <key>LSUIElement</key>
    <false/>
</dict>
</plist>
EOF
