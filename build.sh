#!/bin/bash

rm -rf Video\ Thing.app/
rm Video\ Thing.spec

pip3 install PyQt6

if [ ! -f ./ffmpeg ]; then
  curl -JL -o ffmpeg.zip https://evermeet.cx/ffmpeg/getrelease/zip
  unzip ffmpeg.zip
  rm ffmpeg.zip
fi

if [ ! -f ./ffprobe ]; then
  curl -JL -o ffprobe.zip https://evermeet.cx/ffmpeg/getrelease/ffprobe/zip
  unzip ffprobe.zip
  rm ffprobe.zip
fi

PATH='/Users/cmonahan/Library/Application Support/Herd/bin/:/Users/cmonahan/Library/Application Support/Herd/config/nvm/versions/node/v21.7.3/bin:~/Library/Python/3.9/bin:/usr/local/bin:/System/Cryptexes/App/usr/bin:/usr/bin:/bin:/usr/sbin:/sbin:/var/run/com.apple.security.cryptexd/codex.system/bootstrap/usr/local/bin:/var/run/com.apple.security.cryptexd/codex.system/bootstrap/usr/bin:/var/run/com.apple.security.cryptexd/codex.system/bootstrap/usr/appleinternal/bin'

pyinstaller --hidden-import PyQt6 --hidden-import PyQt6.QtCore --hidden-import PyQt6.QtGui --hidden-import PyQt6.QtWidgets --clean --windowed --name "Video Thing" --add-data="./ffmpeg:." --add-data="./ffprobe:." ./app.py

#if [ -f ./ffmpeg ]; then
  #rm ffmpeg
#fi

#if [ -f ./ffprobe ]; then
  #rm ffprobe
#fi

mv dist/Video\ Thing.app .

rm -rf build
rm -rf dist
