"""Blender EXR (linear, Combined + Depth) -> display image: aerial perspective from the real depth
and camera height, then the same tone curve family as render.grade, so the two engines can be compared.
usage: bl_post.py IN.exr CAMS.json KEY OUT.png [--expo 1.0]"""
import sys, json, math, numpy as np, cv2, OpenEXR

def read_exr(p):
    f = OpenEXR.File(p)
    ch = f.parts[0].channels
    def get(*names):
        for nme in names:
            if nme in ch: return np.asarray(ch[nme].pixels, np.float32)
        raise KeyError(names, list(ch))
    if "ViewLayer.Combined" in ch:
        rgb = get("ViewLayer.Combined")[..., :3]
    else:
        rgb = np.stack([get(f"ViewLayer.Combined.{c}") for c in "RGB"], -1)
    z = get("ViewLayer.Depth.Z", "ViewLayer.Depth.V", "ViewLayer.Depth")
    if z.ndim == 3: z = z[..., 0]
    return rgb, z

def filmic(x):
    a, b, c, d, e = 2.51, 0.03, 2.43, 0.59, 0.14
    return np.clip((x*(a*x+b))/(x*(c*x+d)+e), 0, 1)

def post(rgb, z, cam, expo=1.0, haze_od=0.11, haze_rgb=(0.09, 0.115, 0.15)):
    H, W = z.shape
    tanv = math.tan(math.radians(cam["vfov"])/2); tanh = tanv*W/H
    xs = (np.arange(W)+0.5)/W*2-1; ys = 1-(np.arange(H)+0.5)/H*2
    X, Y = np.meshgrid(xs*tanh, ys*tanv)
    f, u = np.array(cam["fwd"]), np.array(cam["up"]); r = np.cross(f, u)
    d = f[None, None]+X[..., None]*r+Y[..., None]*u
    dz = d[..., 2]/np.linalg.norm(d, axis=-1)
    dist = z*np.linalg.norm(d, axis=-1)                     # Cycles depth is along the view axis
    sky = z > 3e5
    h0 = cam["pos"][2]; Hs = 8000.0
    # optical depth of an exponential atmosphere between camera height and hit height, along the ray
    h1 = np.where(sky, h0+dz*3e5, h0+dz*dist)
    dh = np.where(np.abs(dz) > 1e-4, (np.exp(-np.clip(np.minimum(h0, h1), 0, None)/Hs)-np.exp(-np.maximum(h0, h1)/Hs))*Hs/np.maximum(np.abs(dz), 1e-4), dist*np.exp(-h0/Hs))
    beta = haze_od/Hs                                         # same sea-level extinction as the numpy engine
    T = np.exp(-beta*dh*1.0)[..., None]
    col = rgb*T+np.array(haze_rgb, np.float32)*(1-T)
    x = col*2.85*expo
    lum = (x*np.array([0.2126, 0.7152, 0.0722], np.float32)).sum(-1, keepdims=True)
    x = lum+(x-lum)*1.0
    y = filmic(x)**(1/2.2)
    y = np.clip((y-0.05)/0.95, 0, 1)
    return y*(1-0.42)+(y*y*(3-2*y))*0.42

if __name__ == "__main__":
    a = sys.argv[1:]
    rgb, z = read_exr(a[0]); cam = json.load(open(a[1]))[a[2]]
    expo = float(a[a.index("--expo")+1]) if "--expo" in a else 1.0
    img = post(rgb, z, cam, expo)
    cv2.imwrite(a[3], cv2.cvtColor((np.clip(img, 0, 1)*255+0.5).astype(np.uint8), cv2.COLOR_RGB2BGR))
    print("lin mean", float(rgb.mean()), "z range", float(z.min()), float(np.percentile(z, 99)))
