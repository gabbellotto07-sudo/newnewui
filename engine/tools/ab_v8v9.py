"""v8 (clean delivered video) vs v9 (render_v9 + grade_v9, no graphics) at the same times, side by side.
usage: ab_v8v9.py OUT.jpg t1 t2 ... [--w 960] [--save DIR]   (SELIU_LOOK=warm, SELIU_FMT=16x9)"""
import sys, os, subprocess, numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_v9 as R, grade_v9 as G
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V8 = os.path.join(ROOT, "v8", "seliu-apertura-v8-16x9-1080p-pulita.mp4")
a = sys.argv[1:]; out = a.pop(0)
W = int(a[a.index("--w")+1]) if "--w" in a else 960; H = W*9//16
save = a[a.index("--save")+1] if "--save" in a else None
ts = [float(v) for i, v in enumerate(a) if not v.startswith("--") and (i == 0 or a[i-1] not in ("--w", "--save"))]
L = R.load_levels()

def lab(im, s):
    cv2.putText(im, s, (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(im, s, (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1, cv2.LINE_AA); return im

rows = []
for t in ts:
    f = int(round(t*25))
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", V8, "-vf", f"select=eq(n\\,{f}),scale={W}:{H}", "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True).stdout
    v8 = np.frombuffer(raw, np.uint8).reshape(H, W, 3).copy()
    st = {}; im, m = R.render_frame(t, L, W, H, 1.25, want_matte=True, stats=st)
    im = R.flow_blur(im, t, W, H)
    g = G.finish(G.grade(im, t, m)*R.TL.fade(t), seed=f)
    v9 = cv2.cvtColor(g, cv2.COLOR_RGB2BGR)
    if save:
        os.makedirs(save, exist_ok=True); cv2.imwrite(os.path.join(save, f"v9_t{t:05.2f}.png"), v9)
    rows.append(np.hstack([lab(v8, f"v8  {t:.1f}s"), lab(v9.copy(), f"v9  {t:.1f}s")]))
    print(t, {k: round(float(v), 1) for k, v in st.items()}, flush=True)
cv2.imwrite(out, np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 88])
