#!/bin/bash
# resume the RAW library after the container restart: finish S06, then S07-S09 (2 shards each)
cd "$(dirname "$0")/.."
for S in S06_seliu_topdown S07_seliu_arc S08_pier_to_seliu S09_seliu_hold; do
  mkdir -p frames/shots/$S
  for k in 0 1; do SELIU_SHOT=$S python3 tools/render.py frames frames/shots/$S --clean --matte --w 2560 --h 1440 --ss 1.25 --shard $k/2 > frames/shots/$S.$k.log 2>&1 & done; wait
  echo "$S done $(date)" >> frames/chain3.log
done
echo CHAIN3DONE >> frames/chain3.log
