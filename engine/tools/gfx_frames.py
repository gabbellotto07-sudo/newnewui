"""Phase-1 boards: graded v9 plates (cached as .npy), then graphics A and B on the same frames.
usage: gfx_frames.py OUTDIR t1 t2 ... [--w 1920] [--styles A,B] [--fresh]
  OUTDIR/plate_tXX.XX.npy (graded, float16), OUTDIR/{A,B,clean}_tXX.XX.png (final, with grain)"""
import sys, os, numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_v9 as R, grade_v9 as G, motion_gfx_v9 as M
a = sys.argv[1:]; out = a.pop(0)
W = int(a[a.index("--w")+1]) if "--w" in a else (1920 if R.TL.FMT == "16x9" else 1080)
H = W*9//16 if R.TL.FMT == "16x9" else W*16//9
styles = a[a.index("--styles")+1].split(",") if "--styles" in a else ["A", "B"]
ts = [float(v) for i, v in enumerate(a) if not v.startswith("--") and (i == 0 or a[i-1] not in ("--w", "--styles"))]
os.makedirs(out, exist_ok=True)
L = None
for t in ts:
    f = os.path.join(out, f"plate_t{t:05.2f}.npy")
    if not os.path.exists(f) or "--fresh" in a:
        if L is None: L = R.load_levels()
        im, m = R.render_frame(t, L, W, H, 1.0, want_matte=True)
        im = R.flow_blur(im, t, W, H)
        np.save(f, G.grade(im, t, m).astype(np.float16))
    x = np.load(f).astype(np.float32)
    seed = int(round(t*25))
    cam = R.cam_at(t, W, H)
    cv2.imwrite(os.path.join(out, f"clean_t{t:05.2f}.png"), cv2.cvtColor(G.finish(x*R.TL.fade(t), seed), cv2.COLOR_RGB2BGR))
    for s in styles:
        y = M.draw(x, t, cam, fmt=R.TL.FMT, style=s)
        cv2.imwrite(os.path.join(out, f"{s}_t{t:05.2f}.png"), cv2.cvtColor(G.finish(y*R.TL.fade(t), seed), cv2.COLOR_RGB2BGR))
    print("done", t, flush=True)
