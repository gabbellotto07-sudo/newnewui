"""Seliu v5 opening — renderer.

One continuous camera over a spherical Earth. Ground colour comes from three texture levels
(L0 region, L1 Belitung, L2 Seliu) stored in an azimuthal-equidistant plane centred on Seliu;
each pixel picks the finest level that covers it, with trilinear mip filtering and soft blends,
so there is never a cut between sources. Then: aerial haze, Seliu's light, grade, overlays.

usage:
  render.py frames OUTDIR [--w 1920 --h 1080 --ss 2 --fps 25 --from 0 --to 24]
  render.py stills OUTDIR t1 t2 ...  [--w ...]
"""
import sys, os, json, math, argparse
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(__file__))
from geo import PLACES, LEVELS, LON0, LAT0
import timeline as TL
import overlay as OV

R_E = 6371008.8
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda *p: os.path.join(ROOT, "data", *p)

# ---------------------------------------------------------------- geometry
def ecef(lat, lon, h=0.0):
    la, lo = np.radians(lat), np.radians(lon); r = R_E + h
    return np.stack([r*np.cos(la)*np.cos(lo), r*np.cos(la)*np.sin(lo), r*np.sin(la)], -1)

def enu_basis(lat, lon):
    la, lo = math.radians(lat), math.radians(lon)
    e = np.array([-math.sin(lo), math.cos(lo), 0.0])
    n = np.array([-math.sin(la)*math.cos(lo), -math.sin(la)*math.sin(lo), math.cos(la)])
    u = np.array([math.cos(la)*math.cos(lo), math.cos(la)*math.sin(lo), math.sin(la)])
    return e, n, u

PH0, LM0 = math.radians(LAT0), math.radians(LON0)
def aeqd(lat, lon):
    """spherical azimuthal equidistant around Seliu (metres). Same function for pixels and labels."""
    ph, lm = np.radians(lat), np.radians(lon)
    cosc = np.sin(PH0)*np.sin(ph) + np.cos(PH0)*np.cos(ph)*np.cos(lm-LM0)
    c = np.arccos(np.clip(cosc, -1, 1)); k = np.where(c > 1e-12, c/np.maximum(np.sin(c), 1e-12), 1.0)
    x = R_E*k*np.cos(ph)*np.sin(lm-LM0)
    y = R_E*k*(np.cos(PH0)*np.sin(ph) - np.sin(PH0)*np.cos(ph)*np.cos(lm-LM0))
    return x, y

class Camera:
    def __init__(self, lat, lon, rng, heading, tilt, vfov, W, H):
        self.W, self.H = W, H
        T = ecef(lat, lon)
        e, n, u = enu_basis(lat, lon)
        ps, ts = math.radians(heading), math.radians(tilt)
        hdir = math.sin(ps)*e + math.cos(ps)*n
        fwd = math.sin(ts)*hdir - math.cos(ts)*u
        self.pos = T - rng*fwd
        right = np.cross(fwd, u) if tilt > 1e-3 else np.cross(fwd, hdir)
        # image right: heading direction rotated clockwise 90deg
        right = math.cos(ps)*e - math.sin(ps)*n
        up = np.cross(right, fwd); up /= np.linalg.norm(up)
        right = np.cross(fwd, up); right /= np.linalg.norm(right)
        self.f, self.r, self.u = fwd, right, up
        self.tanv = math.tan(math.radians(vfov)/2); self.tanh = self.tanv*W/H
        self.alt = np.linalg.norm(self.pos) - R_E

    def rays(self):
        xs = (np.arange(self.W)+0.5)/self.W*2-1; ys = 1-(np.arange(self.H)+0.5)/self.H*2
        X, Y = np.meshgrid(xs*self.tanh, ys*self.tanv)
        d = self.f[None, None]+X[..., None]*self.r[None, None]+Y[..., None]*self.u[None, None]
        return d/np.linalg.norm(d, axis=-1, keepdims=True)

    def project(self, P):
        """world points (...,3) -> screen px (...,2), depth (...)"""
        v = P - self.pos; z = v@self.f
        x = (v@self.r)/np.maximum(z, 1e-6)/self.tanh; y = (v@self.u)/np.maximum(z, 1e-6)/self.tanv
        return np.stack([(x+1)/2*self.W, (1-y)/2*self.H], -1), z

    def visible(self, P):
        """not hidden behind the Earth's limb"""
        v = P - self.pos; d = np.linalg.norm(v, axis=-1)
        # P visible if the segment does not dip below the sphere: check angle at P
        n = P/np.linalg.norm(P, axis=-1, keepdims=True)
        return (-(v/d[..., None])*n).sum(-1) > -0.02

# ---------------------------------------------------------------- textures
class Level:
    def __init__(self, name, half, px, path):
        a = np.load(path, mmap_mode="r")
        rgb = np.ascontiguousarray(np.array(a[:3]).transpose(1, 2, 0), dtype=np.float32)
        self.name, self.half, self.px, self.n = name, half, px, rgb.shape[0]
        self.mips = [rgb]
        while self.mips[-1].shape[0] > 64:
            self.mips.append(cv2.pyrDown(self.mips[-1]))
        self.extra = {}

    def add_scalar(self, key, arr):
        m = [arr.astype(np.float32)]
        while m[-1].shape[0] > 64: m.append(cv2.pyrDown(m[-1]))
        self.extra[key] = m

    def coords(self, x, y):
        return ((x+self.half)/self.px-0.5).astype(np.float32), ((self.half-y)/self.px-0.5).astype(np.float32)

    def sample(self, u, v, lod, mips=None, mask=None):
        """trilinear mip sampling, evaluated only where mask is True (others = 0)"""
        mips = mips or self.mips
        ch = 1 if mips[0].ndim == 2 else mips[0].shape[2]
        out = np.zeros(u.shape+((ch,) if ch > 1 else ()), np.float32)
        sel = np.ones(u.shape, bool) if mask is None else mask
        if not sel.any(): return out
        uu, vv = u[sel], v[sel]
        ll = np.clip(lod[sel], 0, len(mips)-1)
        lo = np.floor(ll).astype(np.int32); fr = (ll-lo).astype(np.float32)
        res = np.zeros((uu.size, ch), np.float32)
        for k in np.unique(lo):
            m = lo == k
            for kk, w in ((k, 1-fr[m]), (min(k+1, len(mips)-1), fr[m])):
                s = float(2.0**int(kk))
                mx = ((uu[m]+0.5)/s-0.5).astype(np.float32); my = ((vv[m]+0.5)/s-0.5).astype(np.float32)
                N = mx.size; Wd = 4096; pad = (-N) % Wd
                mx = np.pad(mx, (0, pad)).reshape(-1, Wd); my = np.pad(my, (0, pad)).reshape(-1, Wd)
                r = cv2.remap(mips[kk], mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
                res[m] += r.reshape(-1, ch)[:N]*w[:, None]
        out[sel] = res if ch > 1 else res[:, 0]
        return out

    def edge_weight(self, x, y, feather=0.25):
        e = np.maximum(np.abs(x), np.abs(y))/self.half
        return np.clip((1-e)/feather, 0, 1)

def load_levels():
    L = {}
    for name, half, px in LEVELS:
        p = D(f"{name}_tex.npy") if name != "L2" else D("L2_comp.npy")
        if os.path.exists(p): L[name] = Level(name, half, px, p)
    if "L2" in L and os.path.exists(D("L2_light.npy")):
        L["L2"].add_scalar("light", np.load(D("L2_light.npy")))
    # real clouds of the hero day, faded out softly where the hero scenes end
    for name, rad, fea in (("L2", 26000, 8000), ("L1", 75000, 25000)):
        f = D(f"{name}_clouds.npy")
        if name in L and os.path.exists(f):
            a = np.load(f).astype(np.float32); Lv = L[name]; n = a.shape[0]
            yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
            X = -Lv.half+(xx+.5)*Lv.px; Y = Lv.half-(yy+.5)*Lv.px
            cx, cy = (0.0, 0.0) if name == "L2" else aeqd(np.array(-2.86), np.array(107.93))
            a *= np.clip((rad-np.hypot(X-cx, Y-cy))/fea, 0, 1)
            if name == "L1":   # over Belitung's land the popcorn cumulus read as noise from this height: keep the sea ones
                land = np.load(D("L1_tex.npy"), mmap_mode="r")[3] > 0.5
                a *= 1-cv2.GaussianBlur(cv2.dilate(land.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(np.float32), (0, 0), 3)
            Lv.add_scalar("cloud", a)
    return L

# ---------------------------------------------------------------- look
def filmic(x):
    # gentle ACES-like shoulder, keeps water highlights from clipping
    a, b, c, d, e = 2.51, 0.03, 2.43, 0.59, 0.14
    return np.clip((x*(a*x+b))/(x*(c*x+d)+e), 0, 1)

def grade(rgb, look):
    x = rgb*look["exposure"]
    lum = (x*np.array([0.2126, 0.7152, 0.0722], np.float32)).sum(-1, keepdims=True)
    x = lum+(x-lum)*look["saturation"]
    x = x*np.array(look["balance"], np.float32)
    y = filmic(x)
    y = np.clip(y, 0, 1)**(1/2.2)
    # mild S-curve in display space
    lift = look.get("black", 0.0)
    y = np.clip((y-lift)/(1-lift), 0, 1)
    c = look["contrast"]
    return y*(1-c)+(y*y*(3-2*y))*c


SUN_AZ, SUN_EL = 47.0, 57.0          # Sentinel-2 overpass 29-07-2019 ~10:20 local (computed), shadows fall SW
CLOUD_H = 850.0                      # cumulus height from the real shadow offsets (~530 m) and sun elevation
WIND = (-14.0, 9.0)                  # m/s drift toward NW (south-east monsoon), slightly hastened for the eye

def cloud_alpha(levels, x, y, fp, t, shift=(0.0, 0.0)):
    xs = x+WIND[0]*t+shift[0]; ys = y+WIND[1]*t+shift[1]
    out = np.zeros(x.shape, np.float32); rem = np.ones(x.shape, np.float32)
    for name in ("L2", "L1"):
        if name not in levels or "cloud" not in levels[name].extra: continue
        Lv = levels[name]
        ew = Lv.edge_weight(xs, ys)
        rw = np.clip((np.log2(300)-np.log2(fp))/2, 0, 1) if name == "L2" else np.ones_like(fp)
        w = ew*rw*rem
        if (w > 1e-4).any():
            u, v = Lv.coords(xs, ys); lod = np.log2(np.maximum(fp/Lv.px, 1e-3))
            out += Lv.sample(u, v, lod, Lv.extra["cloud"], mask=w > 1e-4)*w
        rem *= 1-ew*rw
    return out

def sky(d, C, look):
    """space black with the thin blue limb of the atmosphere (seen only in the orbital opening)"""
    b = d@C; rmin = np.sqrt(np.maximum(C@C-b*b, 0))
    h = np.maximum(rmin-R_E, 0)
    glow = np.exp(-h/22000.0)+0.35*np.exp(-h/90000.0)
    base = np.array([0.004, 0.006, 0.012], np.float32)
    limb = np.array([0.18, 0.30, 0.62], np.float32)
    return base+glow[..., None]*limb

def render_frame(t, levels, W, H, ss, look):
    cam_p = TL.camera(t)
    cam = Camera(*cam_p, vfov=TL.VFOV, W=int(round(W*ss)), H=int(round(H*ss)))
    d = cam.rays()
    C = cam.pos
    b = (d@C); cc = C@C-R_E**2; disc = b*b-cc
    hit = disc > 0
    tt = np.where(hit, -b-np.sqrt(np.maximum(disc, 0)), 0)
    P = C[None, None]+d*tt[..., None]
    lat = np.degrees(np.arcsin(np.clip(P[..., 2]/R_E, -1, 1))); lon = np.degrees(np.arctan2(P[..., 1], P[..., 0]))
    x, y = aeqd(lat, lon)
    n = P/R_E; cosi = np.clip(-(d*n).sum(-1), 0.05, 1)
    pix_ang = 2*cam.tanv/cam.H
    fp = tt*pix_ang/np.sqrt(cosi)                       # ground metres per (supersampled) pixel
    col = np.zeros(P.shape, np.float32); wsum = np.zeros(P.shape[:2], np.float32)
    order = ["L2", "L1", "L0", "LG"]
    remaining = np.ones(P.shape[:2], np.float32)
    light = None
    for name in order:
        if name not in levels: continue
        Lv = levels[name]
        ew = Lv.edge_weight(x, y)
        if name == "L2":   # Seliu level: round, generous feather so its real water dissolves into the wider sea
            ew = np.minimum(ew, np.clip((30000-np.hypot(x, y))/14000, 0, 1))
        if name == "L2": rw = np.clip((np.log2(400)-np.log2(fp))/2, 0, 1)
        elif name == "L1": rw = np.clip((np.log2(3500)-np.log2(fp))/2, 0, 1)
        elif name == "L0": rw = np.clip((np.log2(16000)-np.log2(fp))/2, 0, 1)
        else: rw = np.ones_like(fp)
        w = ew*rw*remaining
        if name == "LG" or ("LG" not in levels and name == "L0"): w = remaining
        if (w > 1e-4).any():
            u, v = Lv.coords(x, y); lod = np.log2(np.maximum(fp/Lv.px, 1e-3)) - 0.3
            msk = w > 1e-4
            s = Lv.sample(u, v, lod, mask=msk)
            col += s*w[..., None]; wsum += w
            if name == "L2" and "light" in Lv.extra:
                light = Lv.sample(u, v, lod, Lv.extra["light"], mask=ew > 1e-4)*ew
        remaining = remaining*(1-ew*rw) if w is not remaining else remaining*0
    col /= np.maximum(wsum, 1e-6)[..., None]
    # Seliu in the light: the island and its reef get a touch more sun, the rest a touch less
    gl = TL.glow(t)
    if light is not None and gl > 0:
        k = 1+gl*(0.28*light-0.32*(1-light))
        col *= k[..., None]
        col[..., 0] *= 1+0.06*gl*light; col[..., 1] *= 1+0.02*gl*light; col[..., 2] *= 1-0.04*gl*light
    # shadows of the real clouds (sun from the north-east, 57 deg)
    off = CLOUD_H/math.tan(math.radians(SUN_EL))
    sh = (off*math.sin(math.radians(SUN_AZ)), off*math.cos(math.radians(SUN_AZ)))
    if fp.min() < 2500:
        a_sh = cloud_alpha(levels, x, y, np.maximum(fp, 60.0), t, sh)
        col *= (1-0.55*np.clip(a_sh, 0, 1))[..., None]
    # aerial perspective (exponential atmosphere, H=8 km)
    Hs = 8000.0
    hcam = max(cam.alt, 1.0)
    od_v = look["haze_od"]*(1-math.exp(-hcam/Hs))
    od = od_v/np.maximum(cosi, 0.08)
    T = np.exp(-od)[..., None]
    haze = np.array(look["haze_rgb"], np.float32)
    col = col*T+haze*(1-T)
    # the cloud layer itself, ~850 m up: parallax against the sea as the camera moves
    Rc = R_E+CLOUD_H; disc_c = b*b-(cc+R_E**2-Rc**2)
    if fp.min() < 2500 and cam.alt > CLOUD_H:
        tc = np.where(disc_c > 0, -b-np.sqrt(np.maximum(disc_c, 0)), tt)
        Pc = C[None, None]+d*tc[..., None]
        latc = np.degrees(np.arcsin(np.clip(Pc[..., 2]/Rc, -1, 1))); lonc = np.degrees(np.arctan2(Pc[..., 1], Pc[..., 0]))
        xc, yc = aeqd(latc, lonc)
        fpc = np.maximum(tc*pix_ang/np.sqrt(cosi), 30.0)
        ac = np.clip(cloud_alpha(levels, xc, yc, fpc, t)*1.15, 0, 1)
        if ac.max() > 0.002:
            # sunlit tops, slightly grey-blue in their thin edges
            ccol = np.stack([0.40*(0.80+0.20*ac), 0.41*(0.80+0.20*ac), 0.43*(0.82+0.18*ac)], -1).astype(np.float32)
            Tc = np.exp(-od_v*0.8/np.maximum(cosi, 0.08))[..., None]
            ccol = ccol*Tc+haze*(1-Tc)
            col = col*(1-ac[..., None])+ccol*ac[..., None]
    # beyond the limb: space and the glow of the atmosphere
    if (~hit).any():
        sk = sky(d, C, look)
        edge = np.clip((disc/(np.abs(disc).max()+1e-9))*4000, 0, 1)[..., None]   # soft limb
        col = np.where(hit[..., None], col*edge+sk*(1-edge), sk)
    img = grade(col, look)
    # vignette
    yy, xx = np.mgrid[0:img.shape[0], 0:img.shape[1]].astype(np.float32)
    rr = np.hypot((xx/img.shape[1]-0.5)*1.6, (yy/img.shape[0]-0.5))
    img *= (1-look["vignette"]*np.clip(rr-0.25, 0, 1)**1.6)[..., None]
    img = cv2.resize(img, (W, H), interpolation=cv2.INTER_AREA) if ss > 1 else img
    global LAST_MATTE
    LAST_MATTE = None if light is None else cv2.resize(np.clip(light, 0, 1).astype(np.float32), (W, H), interpolation=cv2.INTER_AREA)
    return img, cam

TRACK_PTS = ["changi", "cgk", "tjq", "belitung_centre", "teluk_gembira_pier", "seliu_landing", "seliu_label", "seliu_south_tip"]
def track(t, cam):
    """screen position (px) of each anchor for this frame, for text/animation in the editor"""
    from geo import PLACES
    out = {}
    for k in TRACK_PTS:
        lon, lat = PLACES[k]
        p, z = cam.project(ecef(lat, lon))
        inside = bool(z > 0 and 0 <= p[0] < cam.W and 0 <= p[1] < cam.H)
        out[k] = [round(float(p[0]), 2), round(float(p[1]), 2), inside]
    return out

def finish_clean(img, k):
    br = np.clip(img.max(-1, keepdims=True)-0.72, 0, 1)
    bloom = cv2.GaussianBlur(br[..., 0], (0, 0), 14*k)[..., None]
    img = np.clip(img+0.22*bloom*np.array([1.0, 0.92, 0.80], np.float32), 0, 1)
    return (img*255+0.5).astype(np.uint8)

def finish(img, t, cam_small, seed):
    # halation: the brightest whites (reef flats, cloud tops) bloom very slightly, warm
    k = min(img.shape[:2])/1080
    br = np.clip(img.max(-1, keepdims=True)-0.72, 0, 1)
    bloom = cv2.GaussianBlur(br[..., 0], (0, 0), 14*k)[..., None]
    img = np.clip(img+0.22*bloom*np.array([1.0, 0.92, 0.80], np.float32), 0, 1)
    # overlays drawn at output size with their own supersampling
    img = OV.draw(img, t, cam_small)
    img = np.clip(img*TL.fade(t), 0, 1)
    rng = np.random.default_rng(seed)
    g = rng.standard_normal(img.shape[:2]).astype(np.float32)
    g = cv2.GaussianBlur(g, (0, 0), 0.6)
    img = np.clip(img+0.011*g[..., None]*(0.6+0.8*img.mean(-1, keepdims=True)), 0, 1)
    return (img*255+0.5).astype(np.uint8)

LAST_MATTE = None
LOOK = json.load(open(os.path.join(ROOT, "tools", "look.json")))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode"); ap.add_argument("out"); ap.add_argument("times", nargs="*", type=float)
    ap.add_argument("--w", type=int, default=1920); ap.add_argument("--h", type=int, default=1080)
    ap.add_argument("--ss", type=float, default=1.5); ap.add_argument("--fps", type=float, default=25)
    ap.add_argument("--from_", type=float, default=0); ap.add_argument("--to", type=float, default=TL.DURATION)
    ap.add_argument("--every", type=int, default=1); ap.add_argument("--clean", action="store_true"); ap.add_argument("--matte", action="store_true"); ap.add_argument("--shard", default="0/1")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    levels = load_levels()
    if a.mode == "stills":
        jobs = [(i, t) for i, t in enumerate(a.times)]
    else:
        n0, n1 = int(round(a.from_*a.fps)), int(round(a.to*a.fps))
        jobs = [(f, f/a.fps) for f in range(n0, n1, a.every)]
    k, K = map(int, a.shard.split("/")); jobs = jobs[k::K]
    for idx, t in jobs:
        if a.mode != "stills" and os.path.exists(os.path.join(a.out, f"f{idx:05d}.png")) and (not a.clean or os.path.exists(os.path.join(a.out, f"f{idx:05d}.json"))) and (not a.matte or os.path.exists(os.path.join(a.out, f"m{idx:05d}.png"))):
            continue                                   # resume after an interruption
        subs = TL.blur_samples(t)
        img = None
        for dt in subs:
            im, _ = render_frame(t+dt, levels, a.w, a.h, a.ss, LOOK)
            img = im if img is None else img+im
        img = img/len(subs)
        cam_s = Camera(*TL.camera(t), vfov=TL.VFOV, W=a.w, H=a.h)
        if a.clean:
            out = finish_clean(img, min(a.w, a.h)/1080)
            cp = TL.camera(t)
            rec = {"frame": idx, "t": round(t, 4), "camera": {"lat": cp[0], "lon": cp[1], "range_m": cp[2], "heading": cp[3], "tilt": cp[4], "vfov": TL.VFOV, "alt_m": cam_s.alt}, "points": track(t, cam_s)}
            with open(os.path.join(a.out, f"f{idx:05d}.json"), "w") as fh: json.dump(rec, fh)
            if a.matte:
                m = LAST_MATTE if LAST_MATTE is not None else np.zeros((a.h, a.w), np.float32)
                cv2.imwrite(os.path.join(a.out, f"m{idx:05d}.png"), (m*255+0.5).astype(np.uint8))
        else:
            out = finish(img, t, cam_s, seed=idx)
        name = f"t{t:06.2f}.png" if a.mode == "stills" else f"f{idx:05d}.png"
        cv2.imwrite(os.path.join(a.out, name), cv2.cvtColor(out, cv2.COLOR_RGB2BGR))
        print(name, f"alt={cam_s.alt/1000:.1f}km", flush=True)

if __name__ == "__main__":
    main()
