#!/bin/bash
# README "Rifarla da zero", steps 1-3 for the wide levels (L2 already built). Resumable: skips existing files.
cd "$(dirname "$0")/.."
export GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR CPL_VSIL_CURL_ALLOWED_EXTENSIONS=.tif GDAL_HTTP_MAX_RETRY=5 GDAL_HTTP_RETRY_DELAY=2
set -e
for a in "LG 6" "L0 8" "L1 11" "L2 13"; do set -- $a; [ -f data/$1_dem.npy ] || python3 tools/fetch_dem.py $1 $2; done
for l in LG L0 L1; do [ -f data/${l}_esa.npy ] || python3 tools/fetch_esa.py $l; done
for s in S2B_48MYB_20190729_1_L2A S2B_48MZB_20190729_0_L2A S2B_48MZC_20190729_0_L2A S2B_48MYC_20190729_0_L2A; do [ -f data/L1_$s.npy ] || python3 tools/fetch_s2.py L1 $s; done
[ -f data/L1_tex.npy ] || python3 tools/build_level.py L1 S2B_48MYB_20190729_1_L2A S2B_48MZB_20190729_0_L2A S2B_48MZC_20190729_0_L2A S2B_48MYC_20190729_0_L2A
[ -f data/L0_tex.npy ] || python3 tools/build_level.py L0
[ -f data/LG_tex.npy ] || python3 tools/build_level.py LG
[ -f data/L1_clouds.npy ] || python3 tools/extract_clouds.py L1 data/L1_tex.npy S2B_48MYB_20190729_1_L2A S2B_48MZB_20190729_0_L2A S2B_48MZC_20190729_0_L2A S2B_48MYC_20190729_0_L2A
if [ ! -f data/.injected ]; then python3 tools/inject.py L2 L1; python3 tools/inject.py L1 L0; python3 tools/inject.py L0 LG; touch data/.injected; fi
echo V5DATA_DONE
