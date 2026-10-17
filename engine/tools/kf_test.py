"""quick look: render_v8 + grade_v8 at given times, side by side. usage: kf_test.py OUT.jpg [--levels L2,LM] t1 t2 ... [--w 960]"""
import sys, os, numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_v8 as R, grade_v8 as G
a = sys.argv[1:]; out = a.pop(0)
lv = tuple(a[a.index("--levels")+1].split(",")) if "--levels" in a else ("LG", "L0", "L1", "LM", "L2")
W = int(a[a.index("--w")+1]) if "--w" in a else 960; H = W*9//16 if R.TL.FMT == "16x9" else W*16//9
ts = [float(v) for i, v in enumerate(a) if (i == 0 or a[i-1] not in ("--levels", "--w")) and not v.startswith("--")]
L = R.load_levels(names=lv)
ims = []
for t in ts:
    st = {}; im, m = R.render_frame(t, L, W, H, 1.25, want_matte=True, stats=st)
    g = G.finish(G.grade(im, t, m), seed=1)
    cv2.putText(g, f"{t:.1f}s  alt {st['alt']/1000:.1f} km", (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    ims.append(cv2.cvtColor(g, cv2.COLOR_RGB2BGR)); print(t, {k: round(float(v), 1) for k, v in st.items()}, flush=True)
cols = 2 if len(ims) > 1 else 1
while len(ims) % cols: ims.append(np.zeros_like(ims[0]))
cv2.imwrite(out, np.vstack([np.hstack(ims[i:i+cols]) for i in range(0, len(ims), cols)]), [cv2.IMWRITE_JPEG_QUALITY, 90])
