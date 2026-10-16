#!/bin/bash
# Package the RAW library: shots (ProRes + mp4 + matte + tracking CSV) and the continuous descent
cd "$(dirname "$0")/.."; R=delivery/raw; mkdir -p $R/shots $R/descent $R/fonts
cp fonts/* $R/fonts/
tocsv() {  # $1 = frames dir, $2 = csv out
python3 - "$1" "$2" <<'PY'
import json, glob, sys, csv
rows = []
for f in sorted(glob.glob(sys.argv[1]+"/f*.json")):
    r = json.load(open(f)); c = r["camera"]
    row = {"frame": r["frame"], "time_s": r["t"], "cam_lat": round(c["lat"], 6), "cam_lon": round(c["lon"], 6), "cam_alt_m": round(c["alt_m"], 1),
           "heading_deg": round(c["heading"], 3), "tilt_deg": round(c["tilt"], 3), "vfov_deg": c["vfov"]}
    for k, (x, y, inside) in r["points"].items():
        ok = abs(x) < 1e5 and abs(y) < 1e5
        row[k+"_x"] = x if ok else ""; row[k+"_y"] = y if ok else ""; row[k+"_inside"] = int(bool(inside) and ok)
    rows.append(row)
w = csv.DictWriter(open(sys.argv[2], "w", newline=""), fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print(sys.argv[2], len(rows))
PY
}
for d in frames/shots/S*/; do
  S=$(basename $d); [ -f $R/shots/${S}.mov ] && continue; grep -q "$S done" frames/chain3.log || { echo "skip $S (not finished)"; continue; }
  ffmpeg -v error -y -framerate 25 -i $d/f%05d.png -c:v prores_ks -profile:v 3 -pix_fmt yuv422p10le -vendor apl0 $R/shots/${S}.mov
  ffmpeg -v error -y -framerate 25 -i $d/f%05d.png -c:v libx264 -preset slow -crf 16 -pix_fmt yuv420p -movflags +faststart $R/shots/${S}.mp4
  ffmpeg -v error -y -framerate 25 -i $d/m%05d.png -c:v libx264 -preset slow -crf 12 -pix_fmt yuv420p $R/shots/${S}_matte.mp4
  tocsv $d $R/shots/${S}_tracking.csv
done
if [ -f frames/raw_16x9/f00624.png ] && [ ! -f $R/descent/tracking-16x9.csv ]; then
  ffmpeg -v error -y -framerate 25 -i frames/raw_16x9/f%05d.png -c:v prores_ks -profile:v 3 -pix_fmt yuv422p10le -vendor apl0 $R/descent/seliu-v5-descent-raw-16x9.mov
  ffmpeg -v error -y -framerate 25 -i frames/raw_16x9/f%05d.png -i audio/sfx_v5.wav -c:v libx264 -preset slow -crf 16 -pix_fmt yuv420p -movflags +faststart -c:a aac -b:a 256k -shortest $R/descent/seliu-v5-descent-raw-16x9.mp4
  tocsv frames/raw_16x9 $R/descent/tracking-16x9.csv
fi
