#!/bin/bash
cd "$(dirname "$0")/.."
until grep -q "S01_orbit_limb done" frames/chain2.log; do sleep 15; done
for p in $(ps -eo pid,comm,args | awk '($2=="chain2.sh") || ($2=="render_shots.sh") || ($2=="python3" && index($0,"SELIU") ) || ($2=="python3" && index($0,"frames/shots/")) {print $1}'); do kill $p 2>/dev/null; done
sleep 3; rm -rf frames/shots/S02_region_nadir_push
# vertical RAW for the 9:16 final cut
for k in 0 1; do SELIU_FMT=9x16 python3 tools/render.py frames frames/raw_9x16 --clean --w 1080 --h 1920 --ss 1.5 --shard $k/2 > frames/raw916_$k.log 2>&1 & done; wait
echo "raw916 done $(date)"
# remaining library shots
for S in S02_region_nadir_push S03_region_to_belitung S04_belitung_rotate S05_belitung_sw_dive S06_seliu_topdown S07_seliu_arc S08_pier_to_seliu S09_seliu_hold; do
  mkdir -p frames/shots/$S
  for k in 0 1; do SELIU_SHOT=$S python3 tools/render.py frames frames/shots/$S --clean --matte --w 2560 --h 1440 --ss 1.25 --shard $k/2 > frames/shots/$S.$k.log 2>&1 & done; wait
  echo "$S done $(date)"
done
echo CHAIN3DONE
