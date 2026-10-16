#!/bin/bash
# v9: rebuild every data file of the v8 from public sources, in the README order. Resumable:
# each step is skipped when its output exists (delete the output to redo a step). Log: data/rebuild.log
set -e
cd "$(dirname "$0")/.."
mkdir -p ../data review; [ -e data ] || ln -s ../data data
export GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR CPL_VSIL_CURL_ALLOWED_EXTENSIONS=.tif,.TIF GDAL_HTTP_MAX_RETRY=8 GDAL_HTTP_RETRY_DELAY=3
step() { echo "=== $(date +%T) $*"; }

# 1. Seliu L2 (10 m): sea 29-07-2019, land August 2026
step L2 scenes
for s in S2B_48MYB_20190729_1_L2A S2B_48MZB_20190729_0_L2A S2B_48MYB_20190818_0_L2A S2B_48MZB_20190818_0_L2A \
         S2B_48MYB_20240712_0_L2A S2B_48MYB_20230618_0_L2A S2A_48MYB_20260808_0_L2A S2C_48MYB_20260826_0_L2A \
         S2B_48MYB_20260801_0_L2A S2C_48MYB_20250702_0_L2A; do [ -f data/L2_$s.npy ] || python3 tools/fetch_s2.py L2 $s; done
if [ ! -f data/L2_comp_2019land.npy ]; then
  step L2 composite
  python3 tools/composite.py L2 data/L2_comp.npy S2B_48MYB_20190729_1_L2A S2B_48MZB_20190729_0_L2A S2B_48MYB_20190818_0_L2A S2B_48MZB_20190818_0_L2A S2B_48MYB_20240712_0_L2A S2B_48MYB_20230618_0_L2A
  cp data/L2_comp.npy data/L2_comp_2019land.npy
  python3 tools/land_update.py S2A_48MYB_20260808_0_L2A S2C_48MYB_20260826_0_L2A S2B_48MYB_20260801_0_L2A S2C_48MYB_20250702_0_L2A S2B_48MYB_20240712_0_L2A
fi
[ -f data/L2_light.npy ] || python3 tools/make_light.py
[ -f data/L2_clouds.npy ] || python3 tools/extract_clouds.py L2 data/L2_comp_2019land.npy S2B_48MYB_20190729_1_L2A S2B_48MZB_20190729_0_L2A
[ -f data/seliu_outline_lonlat.json ] || python3 tools/make_outline.py

# 2. wide levels LG / L0 / L1
step wide levels
tools/fetch_all_v5.sh

# 3. Belitung LM (15 m) and relief
step LM
for d in "20190729 S2B" "20260808 S2A" "20260801 S2B" "20260806 S2C" "20260811 S2B" "20260826 S2C" "20260920 S2B" "20260722 S2B" "20260622 S2B"; do
  set -- $d; [ -f data/LM_$1.npy ] || python3 tools/fetch_lm.py $1 $2; done
[ -f data/L2_cop.npy ] || python3 tools/fetch_cop.py L2
[ -f data/LM_cop.npy ] || python3 tools/fetch_cop.py LM
[ -f data/LM_tex.npy ] || python3 tools/build_lm.py 20190729 20260808 20260801 20260806 20260811 20260826 20260920 20260722 20260622
if [ ! -f data/.injected_v8 ]; then
  step rebuild L0 LG + exact injection
  python3 tools/build_level.py L0; python3 tools/build_level.py LG
  python3 tools/inject_v8.py LM L1; python3 tools/inject_v8.py L1 L0; python3 tools/inject_v8.py L0 LG
  touch data/.injected_v8
fi

# 4. Himawari-8, 29-07-2019 03:20 UTC (orbit and region clouds), NOAA open data
step Himawari
mkdir -p data/himawari
B=https://noaa-himawari8.s3.amazonaws.com/AHI-L1b-FLDK/2019/07/29/0320
for band in B01:R10 B02:R10 B03:R10 B13:R20; do      # full-disk single files; B03 at 1 km like B01/B02
  b=${band%:*}; r=${band#*:}; f=HS_H08_20190729_0320_${b}_FLDK_${r}_S0101.DAT
  [ -f data/himawari/$f ] || { curl -sSf --retry 5 -o data/himawari/$f.bz2 $B/$f.bz2 && bunzip2 -f data/himawari/$f.bz2; }
done
[ -f data/L0_hcloud.npy ] || python3 tools/build_himawari.py LG L0
step DATA_DONE
