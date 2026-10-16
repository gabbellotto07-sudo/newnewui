"""Composite RAW plate -> cinematic grade -> motion graphics -> fade -> film grain.

usage:
  gfx_comp.py stills OUTDIR t1 t2 ...  [--fmt 16x9] [--sheet]     nearest available RAW frame per time
  gfx_comp.py frames OUTDIR [--from 0 --to 624 --fmt 16x9]          full sequence (PNG, 8-bit RGB)

RAW plates: frames/raw_16x9 or frames/raw_9x16 (fNNNNN.png + fNNNNN.json with the camera).
"""
import os, sys, json, argparse, time
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import grade_cine as G
import motion_gfx as M
from render import Camera

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS = 25

def fade(t):                     # picture up from black after the first sound (same as timeline.fade)
    x = min(max((t-0.05)/0.95, 0), 1); return x*x*(3-2*x)

def load(fmt, i):
    d = os.path.join(ROOT, "frames", f"raw_{fmt}")
    img = cv2.imread(os.path.join(d, f"f{i:05d}.png"), cv2.IMREAD_COLOR)
    meta = json.load(open(os.path.join(d, f"f{i:05d}.json")))
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32)/255.0, meta

def camera(meta, W, H):
    c = meta["camera"]
    return Camera(c["lat"], c["lon"], c["range_m"], c["heading"], c["tilt"], vfov=c["vfov"], W=W, H=H)

def nearest(fmt, i):
    d = os.path.join(ROOT, "frames", f"raw_{fmt}")
    for o in range(0, 6):
        for j in (i-o, i+o):
            if os.path.exists(os.path.join(d, f"f{j:05d}.png")) and os.path.exists(os.path.join(d, f"f{j:05d}.json")):
                return j
    raise FileNotFoundError(i)

def comp(fmt, i, timing=None):
    img, meta = load(fmt, i)
    H, W = img.shape[:2]; t = meta["t"]
    t0 = time.time(); x = G.grade(img, t); t1 = time.time()
    x = M.draw(x, t, camera(meta, W, H), fmt=fmt); t2 = time.time()
    x = x*fade(t)
    out = G.finish(x, seed=i); t3 = time.time()
    if timing is not None: timing.append((t1-t0, t2-t1, t3-t2))
    return out, t

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode"); ap.add_argument("out"); ap.add_argument("times", nargs="*", type=float)
    ap.add_argument("--fmt", default="16x9"); ap.add_argument("--from_", type=int, default=0); ap.add_argument("--to", type=int, default=624)
    ap.add_argument("--sheet", action="store_true")
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    timing = []; names = []
    if a.mode == "stills":
        for t in a.times:
            i = nearest(a.fmt, int(round(t*FPS)))
            out, tt = comp(a.fmt, i, timing)
            n = os.path.join(a.out, f"{a.fmt}_f{i:05d}_t{tt:05.2f}.png"); names.append((n, tt, i))
            cv2.imwrite(n, cv2.cvtColor(out, cv2.COLOR_RGB2BGR)); print(n, "grade %.2fs gfx %.2fs finish %.2fs" % timing[-1], flush=True)
    else:
        for i in range(a.from_, a.to+1):
            out, tt = comp(a.fmt, i, timing)
            cv2.imwrite(os.path.join(a.out, f"f{i:05d}.png"), cv2.cvtColor(out, cv2.COLOR_RGB2BGR))
    if a.sheet and names:
        ims = []
        for n, tt, i in names:
            im = cv2.imread(n); h, w = im.shape[:2]; s = 640/max(w, h)
            im = cv2.resize(im, (int(w*s), int(h*s)), interpolation=cv2.INTER_AREA)
            cv2.putText(im, f"t={tt:.2f}s f{i}", (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(im, f"t={tt:.2f}s f{i}", (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
            ims.append(im)
        cols = 3 if ims[0].shape[1] > ims[0].shape[0] else 5
        while len(ims) % cols: ims.append(np.zeros_like(ims[0]))
        rows = [np.hstack(ims[r:r+cols]) for r in range(0, len(ims), cols)]
        cv2.imwrite(os.path.join(a.out, "sheet.jpg"), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 88])

if __name__ == "__main__":
    main()
