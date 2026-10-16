#!/bin/bash
# v9 animatic: 960x540 and 540x960 frames + provisional ambience (web mix -16 LUFS) -> v9/review/f2/
cd "$(dirname "$0")/../.."
mkdir -p v9/review/f2
for F in 16x9 9x16; do
  ffmpeg -v error -y -framerate 25 -i frames/anim_$F/f%05d.png -i v9/audio/animatic-ambiente-web-${F}_-16LUFS.wav \
    -c:v libx264 -preset slow -crf 20 -pix_fmt yuv420p -movflags +faststart -c:a aac -b:a 192k -shortest \
    v9/review/f2/seliu-v9-animatic-$F.mp4
done
echo ENCODED
