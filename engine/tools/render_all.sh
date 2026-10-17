#!/bin/bash
# Final renders, 3 shards per format (memory-safe on a 16 GB machine)
cd "$(dirname "$0")/.."
for k in 0 1 2; do python3 tools/render.py frames frames/final_16x9 --w 1920 --h 1080 --ss 1.5 --shard $k/3 > frames/r169_$k.log 2>&1 & done; wait
for k in 0 1 2; do SELIU_FMT=9x16 python3 tools/render.py frames frames/final_9x16 --w 1080 --h 1920 --ss 1.5 --shard $k/3 > frames/r916_$k.log 2>&1 & done; wait
echo ALLDONE
