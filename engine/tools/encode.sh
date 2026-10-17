#!/bin/bash
# Mux final frames + sound into the delivery files
cd "$(dirname "$0")/.."; mkdir -p delivery
for F in 16x9 9x16; do
  ffmpeg -v error -y -framerate 25 -i frames/final_$F/f%05d.png -i audio/sfx_v5.wav \
    -c:v libx264 -preset slow -crf 14 -profile:v high -pix_fmt yuv420p -movflags +faststart \
    -c:a aac -b:a 256k -shortest delivery/seliu-apertura-v5-$F.mp4
  ffmpeg -v error -y -framerate 25 -i frames/final_$F/f%05d.png \
    -c:v libx264 -preset slow -crf 12 -profile:v high -pix_fmt yuv420p -movflags +faststart \
    delivery/seliu-apertura-v5-$F-nosound.mp4
done
cp audio/sfx_v5.wav delivery/seliu-apertura-v5-sfx.wav
