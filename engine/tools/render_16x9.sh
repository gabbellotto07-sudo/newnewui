#!/bin/bash
# v8 16:9 master, 1920x1080, 25 fps, 28 s: graded + graphics, and the clean (no text) version. Resumable.
cd "$(dirname "$0")/.."
export SELIU_FMT=16x9 SELIU_LOOK=warm
rm -f ../frames/v8_16x9/done
python3 tools/render_v8.py frames ../frames/v8_16x9 --final --clean_dir ../frames/v8_16x9_clean \
   --w 1920 --h 1080 --ss 1.0 --workers 2 > ../frames/v8_16x9/render.log 2>&1
echo RENDER16_DONE > ../frames/v8_16x9/done
