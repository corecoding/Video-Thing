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
DIR=$(cd "$(dirname "$0")" && pwd)

# Get Resources directory
RESOURCES_DIR="$(dirname "$DIR")/Resources"
if [ ! -d "$RESOURCES_DIR" ]; then
    echo "ERROR: Resources directory not found at $RESOURCES_DIR"
    exit 1
fi

# Path to Python virtual environment
VENV_DIR="$DIR/venv"

# Check if this is the first run
FIRST_RUN_FLAG="$DIR/.installed"
if [ ! -f "$FIRST_RUN_FLAG" ]; then
    # Remove any existing environment
    if [ -d "$VENV_DIR" ]; then
        rm -rf "$VENV_DIR"
    fi

    # Create a fresh environment
    python3 -m venv "$VENV_DIR"

    # Install required packages
    "$VENV_DIR/bin/pip" install --upgrade pip
    "$VENV_DIR/bin/pip" install PyQt6 setuptools

    # Create flag file to indicate we've run the setup
    touch "$FIRST_RUN_FLAG"
fi

# Run the app from the virtual environment
cd "$DIR" && "$DIR/venv/bin/python3" "$RESOURCES_DIR/app.py"
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
