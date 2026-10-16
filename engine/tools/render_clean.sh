#!/bin/bash
# RAW renders: no text, no fade, no grain (+ per-frame tracking JSON of the anchors)
cd "$(dirname "$0")/.."
for k in 0 1 2; do python3 tools/render.py frames frames/raw_16x9 --clean --w 1920 --h 1080 --ss 1.5 --shard $k/3 > frames/raw169_$k.log 2>&1 & done; wait
for k in 0 1 2; do SELIU_FMT=9x16 python3 tools/render.py frames frames/raw_9x16 --clean --w 1080 --h 1920 --ss 1.5 --shard $k/3 > frames/raw916_$k.log 2>&1 & done; wait
echo ALLDONE
