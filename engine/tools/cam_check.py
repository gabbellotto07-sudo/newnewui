"""where the anchors fall on screen along the flight (no rendering): fraction of width/height, '-' = off screen
usage: cam_check.py [t0 t1 step]   (SELIU_FMT selects the format)"""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_v8 as R, timeline_v8 as TL
from geo import PLACES
from render import ecef
W, H = (1920, 1080) if TL.FMT == "16x9" else (1080, 1920)
keys = ["changi", "cgk", "tjq", "belitung_centre", "seliu_label", "teluk_gembira_pier", "seliu_landing"]
a = [float(x) for x in sys.argv[1:4]] if len(sys.argv) > 3 else [0, TL.DURATION, 1.0]
print("t     alt_km  " + "  ".join(f"{k[:10]:>11}" for k in keys) + "  speed_px/f")
for t in np.arange(a[0], a[1]+1e-6, a[2]):
    c = R.cam_at(t, W, H); row = []
    for k in keys:
        lon, lat = PLACES[k]; p, z = c.project(ecef(lat, lon))
        ok = z > 0 and 0 <= p[0] <= W and 0 <= p[1] <= H and c.visible(ecef(lat, lon))
        row.append(f"{p[0]/W:4.2f},{p[1]/H:4.2f}" if ok else "     -     ")
    med, mx = R.screen_speed(t, W, H)
    print(f"{t:5.1f} {c.alt/1000:8.1f}  " + "  ".join(f"{r:>11}" for r in row) + f"  {med:6.1f} {mx:6.1f}")
