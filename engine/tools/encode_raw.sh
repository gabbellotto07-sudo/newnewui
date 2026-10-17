#!/bin/bash
# RAW delivery: ProRes 422 HQ + H.264 preview + tracking CSV, both formats
cd "$(dirname "$0")/.."; mkdir -p delivery/raw delivery/reference
for F in 16x9 9x16; do
  ffmpeg -v error -y -framerate 25 -i frames/raw_$F/f%05d.png -c:v prores_ks -profile:v 3 -pix_fmt yuv422p10le -vendor apl0 delivery/raw/seliu-v5-raw-$F.mov
  ffmpeg -v error -y -framerate 25 -i frames/raw_$F/f%05d.png -c:v libx264 -preset slow -crf 14 -pix_fmt yuv420p -movflags +faststart delivery/raw/seliu-v5-raw-$F.mp4
  python3 - "$F" <<'PY'
import json, glob, sys, csv
F = sys.argv[1]; rows = []
for f in sorted(glob.glob(f"frames/raw_{F}/f*.json")):
    r = json.load(open(f)); c = r["camera"]
    row = {"frame": r["frame"], "time_s": r["t"], "cam_lat": round(c["lat"], 6), "cam_lon": round(c["lon"], 6),
           "cam_alt_m": round(c["alt_m"], 1), "heading_deg": round(c["heading"], 3), "tilt_deg": round(c["tilt"], 3), "vfov_deg": c["vfov"]}
    for k, (x, y, inside) in r["points"].items():
        ok = abs(x) < 1e5 and abs(y) < 1e5
        row[f"{k}_x"] = x if ok else ""; row[f"{k}_y"] = y if ok else ""; row[f"{k}_inside"] = int(inside and ok)
    rows.append(row)
with open(f"delivery/raw/tracking-{F}.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print(F, len(rows), "frames tracked")
PY
done
cp audio/sfx_v5.wav delivery/seliu-apertura-v5-sfx.wav
