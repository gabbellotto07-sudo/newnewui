"""Render the numpy engine (render.py) from an explicit camera, clean (no overlays), for A/B tests.
usage: ab_engineA.py CAMS.json KEY OUT.png [--w 960 --h 540 --ss 1.5 --t 24.9]"""
import sys, os, json, time, numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render as R, timeline as TL
a = sys.argv[1:]; c = json.load(open(a[0]))[a[1]]
o = lambda k, d, f=float: f(a[a.index(k)+1]) if k in a else d
W, H, ss, t = o("--w", 960, int), o("--h", 540, int), o("--ss", 1.5), o("--t", c.get("t", 0.0))
TL.camera = lambda _t: tuple(c["params"]); TL.VFOV = c["vfov"]
lv = R.load_levels(); t0 = time.time()
img, _ = R.render_frame(t, lv, W, H, ss, R.LOOK)
print("engineA %.1fs" % (time.time()-t0))
cv2.imwrite(a[2], cv2.cvtColor(R.finish_clean(img, min(W, H)/1080), cv2.COLOR_RGB2BGR))
