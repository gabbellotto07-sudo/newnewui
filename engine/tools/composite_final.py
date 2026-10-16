"""Final cut compositor: RAW plate frames (+ per-frame camera JSON) -> cinematic grade -> motion graphics -> grain.
usage: composite_final.py RAW_DIR OUT_DIR [--fmt 16x9] [--shard k/K] [--times t1 t2 ...]"""
import sys, os, json, argparse, numpy as np, cv2
sys.path.insert(0, os.path.dirname(__file__))
import render as R, grade_cine as G, motion_gfx as M, timeline as TL
ap = argparse.ArgumentParser(); ap.add_argument("raw"); ap.add_argument("out"); ap.add_argument("--fmt", default="16x9")
ap.add_argument("--shard", default="0/1"); ap.add_argument("--times", nargs="*", type=float)
a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
frames = sorted(f for f in os.listdir(a.raw) if f.startswith("f") and f.endswith(".png"))
if a.times: frames = [f"f{int(round(t*25)):05d}.png" for t in a.times]
k, K = map(int, a.shard.split("/"))
for fn in frames[k::K]:
    idx = int(fn[1:6]); t = idx/25.0
    img = cv2.cvtColor(cv2.imread(os.path.join(a.raw, fn)), cv2.COLOR_BGR2RGB).astype(np.float32)/255.0
    H, W = img.shape[:2]
    c = json.load(open(os.path.join(a.raw, fn.replace(".png", ".json"))))["camera"]
    cam = R.Camera(c["lat"], c["lon"], c["range_m"], c["heading"], c["tilt"], vfov=c["vfov"], W=W, H=H)
    img = G.grade(img, t)
    img = M.draw(img, t, cam, fmt=a.fmt)
    img = img*TL.fade(t) if not os.environ.get("NOFADE") else img
    out = G.finish(img, seed=idx)
    out = (np.clip(out, 0, 1)*255+0.5).astype(np.uint8) if out.dtype != np.uint8 else out
    cv2.imwrite(os.path.join(a.out, fn), cv2.cvtColor(out, cv2.COLOR_RGB2BGR))
    print(fn, flush=True)
