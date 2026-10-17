#!/bin/bash
cd "$(dirname "$0")/.."
# 1. missing raw 16:9 frames (shard killed by OOM): all frames = 2 mod 3 from 320
python3 tools/render.py frames frames/raw_16x9 --clean --w 1920 --h 1080 --ss 1.5 --from_ 12.8 --to 18.8 --shard 0/3 > frames/fill_a.log 2>&1 &
python3 tools/render.py frames frames/raw_16x9 --clean --w 1920 --h 1080 --ss 1.5 --from_ 18.8 --to 25 --shard 0/3 > frames/fill_b.log 2>&1 &
wait; echo "fill done $(date)"
# 2. raw library shots (2 at a time)
tools/render_shots.sh
# 3. raw vertical descent for the 9:16 final cut
for k in 0 1; do SELIU_FMT=9x16 python3 tools/render.py frames frames/raw_9x16 --clean --w 1080 --h 1920 --ss 1.5 --shard $k/2 > frames/raw916_$k.log 2>&1 & done; wait
echo CHAIN2DONE
