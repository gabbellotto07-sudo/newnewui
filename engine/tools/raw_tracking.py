"""Seliu v9 raw — per-frame 2D tracking of the key places, from the same camera as the render (no render needed).
Columns per place: x, y (px, 1920x1080, origin top-left, may be outside the frame), vis (1 = in front of the camera,
not behind the globe, inside the frame), dist_km (camera to the place).
usage: raw_tracking.py OUT.csv [W H]"""
import sys, os, csv, json, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_v9 as R
from render import ecef
from geo import PLACES
TL = R.TL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ol = np.array(json.load(open(os.path.join(ROOT, "data", "seliu_outline_lonlat.json")))["lonlat"], float)
SELIU_C = (float(ol[:, 0].mean()), float(ol[:, 1].mean()))
PTS = [("singapore_changi", PLACES["changi"]), ("jakarta_cgk", PLACES["cgk"]), ("arrival_airport_tanjung_pandan", PLACES["tjq"]),
       ("belitung_centre", PLACES["belitung_centre"]), ("teluk_gembira_pier", PLACES["teluk_gembira_pier"]),
       ("seliu_jetty", PLACES["seliu_landing"]), ("seliu_centre", SELIU_C)]

def main():
    out = sys.argv[1]; W = int(sys.argv[2]) if len(sys.argv) > 2 else 1920; H = int(sys.argv[3]) if len(sys.argv) > 3 else 1080
    P = {k: ecef(lat, lon) for k, (lon, lat) in PTS}
    n = int(round((TL.DURATION-TL.T_START)*TL.FPS))
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["frame", "time_s"]+[f"{k}_{c}" for k, _ in PTS for c in ("x", "y", "vis", "dist_km")])
        for f in range(n):
            t = TL.T_START+f/TL.FPS
            c = R.cam_at(t, W, H)
            row = [f, f"{f/TL.FPS:.2f}"]
            for k, _ in PTS:
                p, z = c.project(P[k]); vis = bool(z > 0 and c.visible(P[k]) and 0 <= p[0] < W and 0 <= p[1] < H)
                row += [f"{p[0]:.2f}", f"{p[1]:.2f}", int(vis), f"{np.linalg.norm(P[k]-c.pos)/1000:.3f}"]
            w.writerow(row)
    print("tracking", n, "frames ->", out, "seliu centre", SELIU_C)

if __name__ == "__main__":
    main()
