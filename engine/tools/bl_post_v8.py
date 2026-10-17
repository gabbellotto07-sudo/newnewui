"""Blender EXR (linear Combined + Depth) -> the same v8 chain as the numpy engine: render_v8.atmosphere
(using the real hit height and distance), render_v8.tone, grade_v8, grain. For an honest A/B.
usage: bl_post_v8.py IN.exr CAMS.json KEY OUT.png [--expo 0.93]"""
import sys, os, json, math, numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bl_post, bl_prep as B, render_v8 as R, grade_v8 as G

def main():
    a = sys.argv[1:]
    rgb, z = bl_post.read_exr(a[0]); cam = json.load(open(a[1]))[a[2]]
    expo = float(a[a.index("--expo")+1]) if "--expo" in a else 0.93
    H, W = z.shape
    tanv = math.tan(math.radians(cam["vfov"])/2); tanh = tanv*W/H
    xs = (np.arange(W)+0.5)/W*2-1; ys = 1-(np.arange(H)+0.5)/H*2
    X, Y = np.meshgrid(xs*tanh, ys*tanv)
    f, u = np.array(cam["fwd"]), np.array(cam["up"]); r = np.cross(f, u)
    d = f[None, None]+X[..., None]*r+Y[..., None]*u
    nd = np.linalg.norm(d, axis=-1); dist = z*nd; d = d/nd[..., None]
    P = np.array(cam["pos"])[None, None]+d*dist[..., None]
    Pe = B.O0+P[..., 0:1]*B.E0+P[..., 1:2]*B.N0+P[..., 2:3]*B.U0          # back to ECEF
    rr = np.linalg.norm(Pe, axis=-1); h_hit = (rr-R.R_E).astype(np.float32)
    nrm = Pe/rr[..., None]
    de = d[..., 0:1]*B.E0+d[..., 1:2]*B.N0+d[..., 2:3]*B.U0
    mu = np.clip(-(de*nrm).sum(-1), 0.02, 1).astype(np.float32)
    t = cam["t"]
    col = rgb.astype(np.float32)*expo
    col = R.bright_knee(col)
    col = R.atmosphere(col, de.astype(np.float32), cam["alt"], np.clip(h_hit, 0, None), mu, None, R.TL.warmth(t))
    img = R.tone(col)
    out = G.finish(G.grade(img, t), seed=1)
    cv2.imwrite(a[3], cv2.cvtColor(out, cv2.COLOR_RGB2BGR))
    print("written", a[3])

if __name__ == "__main__":
    main()
