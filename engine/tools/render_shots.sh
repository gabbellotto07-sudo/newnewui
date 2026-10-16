#!/bin/bash
# Raw library: 9 slow shots, 2560x1440, no text/grain/fade, neutral grade (no Seliu light: use the matte pass)
cd "$(dirname "$0")/.."
for S in $(python3 -c "import json;print(' '.join(k for k in json.load(open('tools/shots.json')) if not k.startswith('_')))"); do
  mkdir -p frames/shots/$S
  for k in 0 1; do SELIU_SHOT=$S python3 tools/render.py frames frames/shots/$S --clean --matte --w 2560 --h 1440 --ss 1.25 --shard $k/2 > frames/shots/$S.$k.log 2>&1 & done; wait
  echo "$S done $(date)"
done
echo SHOTSDONE
