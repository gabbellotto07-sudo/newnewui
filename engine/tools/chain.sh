#!/bin/bash
cd "$(dirname "$0")/.."
until [ $(ls frames/raw_16x9 | grep -c png) -ge 625 ]; do sleep 15; done
for p in $(ps -eo pid,comm,args | awk '($2=="render_clean.sh") || ($2=="python3" && index($0,"raw_9x16")) {print $1}'); do kill $p; done
sleep 3; tools/render_shots.sh
