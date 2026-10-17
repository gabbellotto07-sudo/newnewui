#!/bin/bash
# encode the v8 16:9 master (with text) and the clean version, with the ambience mix
cd "$(dirname "$0")/../.."
A=v8/audio/stems/ambience_16x9.wav
ffmpeg -v error -y -framerate 25 -i frames/v8_16x9/f%05d.png -i $A -c:v libx264 -preset slow -crf 15 -profile:v high -pix_fmt yuv420p \
  -x264-params "aq-mode=3:deblock=-1,-1" -movflags +faststart -c:a aac -b:a 320k -shortest v8/seliu-apertura-v8-16x9-1080p.mp4
ffmpeg -v error -y -framerate 25 -i frames/v8_16x9_clean/f%05d.png -i $A -c:v libx264 -preset slow -crf 15 -profile:v high -pix_fmt yuv420p \
  -x264-params "aq-mode=3:deblock=-1,-1" -movflags +faststart -c:a aac -b:a 320k -shortest v8/seliu-apertura-v8-16x9-1080p-pulita.mp4
cp $A v8/audio/seliu-v8-mix-ambiente-16x9.wav
echo ENCODED
