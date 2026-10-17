"""Seliu v9 renderer = v8 renderer with the image corrections of the v9 brief:
  * regional clouds (Himawari-8) coloured by their own measured brightness (same instant, same sun),
    soft physical edges, cooler shade: volume instead of flat white patches
  * the added sun glint almost removed (Sentinel-2 already carries the real one)
  * Belitung from its real 15 m level (LM, mipmapped) up to ~500 m per pixel, not the 100 m class map
  * less coloured haze on the ground in the descent (TL.haze), sky and limb unchanged
(v8 header follows)
Seliu v8 renderer: one physical camera over the real, round Earth.

What is new against render.py (v5):
  * five coaxial texture levels LG, L0, L1, LM (Belitung at 15 m, new), L2 (Seliu at 10 m), stored
    as uint16 mip pyramids, picked per pixel by ground footprint with soft blends (no visible switch)
  * real relief: Copernicus GLO-30 heights move the ground along the view ray (true parallax on the
    Belitung hills and on Seliu's canopy), no exaggeration
  * a physical-ish atmosphere: Rayleigh + Mie with their own scale heights, transmittance and
    in-scattering integrated along every ray, sun phase (brighter toward the sun), a real sky and
    horizon at low altitude, the limb from orbit
  * the real cumulus of 29-07-2019 as 2.5D volumes: dome heights from each cloud's own size, flat
    bases at ~750 m, sunlit tops, shadowed flanks, soft edges, ground shadows from the real sun
  * camera roll (bank) and adaptive motion blur from the real screen speed

usage:
  render_v8.py stills OUT t1 t2 ... [--w 1920 --h 1080 --ss 1.25]   -> OUT/tXX.XX.png (+ .json camera)
  render_v8.py frames OUT [--from_ 0 --to 28 --shard k/K --w --h --ss]  resumable: skips finished frames
Output is the display-referred RAW plate (tone mapped, no grade, no graphics) as 16-bit PNG,
or with --final the full chain (grade_v8 -> motion_gfx -> fade -> grain) as 8-bit PNG.
"""
import sys, os, json, math, time, argparse
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render as R5
from render import ecef, enu_basis, aeqd, R_E
from geo import LEVELS
import timeline_v9 as TL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda *p: os.path.join(ROOT, "data", *p)

SUN_AZ, SUN_EL = 46.0, 57.5                     # 29-07-2019 03:20 UTC at Seliu (computed)
CLOUD_BASE = 720.0                              # flat cumulus bases; tops reach ~850-1000 m (shadow-derived ~850 m)
DOME_MAX = 420.0
WIND = (-6.0, 4.0)                              # m/s, south-east monsoon drift (slow: real cumulus barely move in 28 s)
# atmosphere (sea-level extinction per metre, scale heights): tropical, humid, gentle
BR, HR = np.array([5.8e-6, 13.5e-6, 33.1e-6], np.float32)*0.38, 8000.0
BM, HM = 1.5e-5, 1200.0
SKY_R = np.array([0.16, 0.24, 0.42], np.float32)     # in-scatter radiance per unit (1-T), reflectance units
SKY_M = np.array([0.20, 0.196, 0.185], np.float32)

# ------------------------------------------------------------------ camera with bank
class Camera(R5.Camera):
    def __init__(self, lat, lon, rng, heading, tilt, vfov, W, H, roll=0.0):
        super().__init__(lat, lon, rng, heading, tilt, vfov, W, H)
        if roll:
            cr, sr = math.cos(math.radians(roll)), math.sin(math.radians(roll))
            r, u = self.r, self.u
            self.r, self.u = cr*r-sr*u, sr*r+cr*u

def cam_at(t, W, H):
    p = TL.camera(t)
    c = Camera(*p[:5], vfov=TL.VFOV, W=W, H=H, roll=p[5])
    a = math.radians(TL.look_up(t)) if hasattr(TL, "look_up") else 0.0
    if a:                                     # raw: before t=0 the camera looks above the Earth, tilting down
        f, u = c.f, c.u
        c.f, c.u = math.cos(a)*f+math.sin(a)*u, math.cos(a)*u-math.sin(a)*f
    return c

# ------------------------------------------------------------------ textures (uint16 mip pyramids)
class Tex:
    def __init__(self, arr, half, px, scale):
        a = np.clip(np.asarray(arr, np.float32)*scale+0.5, 0, 65535).astype(np.uint16)
        self.half, self.px, self.scale = half, px, scale
        self.mips = [a]
        while self.mips[-1].shape[0] > 64:
            self.mips.append(cv2.pyrDown(self.mips[-1]))
        self.ch = 1 if a.ndim == 2 else a.shape[2]

    def edge(self, x, y, feather=0.25):
        e = np.maximum(np.abs(x), np.abs(y))/self.half
        return np.clip((1-e)/feather, 0, 1)

    def sample(self, x, y, fp, mask=None, bias=0.0):
        """trilinear mip sampling at ground footprint fp (m), evaluated only where mask"""
        out = np.zeros(x.shape+((self.ch,) if self.ch > 1 else ()), np.float32)
        sel = np.ones(x.shape, bool) if mask is None else mask
        if not sel.any(): return out
        uu = ((x[sel]+self.half)/self.px-0.5).astype(np.float32); vv = ((self.half-y[sel])/self.px-0.5).astype(np.float32)
        ll = np.clip(np.log2(np.maximum(fp[sel] if np.ndim(fp) else np.full(uu.shape, fp), 1e-3)/self.px)+bias, 0, len(self.mips)-1)
        lo = np.floor(ll).astype(np.int32); fr = (ll-lo).astype(np.float32)
        res = np.zeros((uu.size, self.ch), np.float32)
        for k in np.unique(lo):
            m = lo == k
            for kk, w in ((k, 1-fr[m]), (min(k+1, len(self.mips)-1), fr[m])):
                s = float(2.0**int(kk))
                mx = ((uu[m]+0.5)/s-0.5).astype(np.float32); my = ((vv[m]+0.5)/s-0.5).astype(np.float32)
                N = mx.size; Wd = 4096; pad = (-N) % Wd
                mx = np.pad(mx, (0, pad)).reshape(-1, Wd); my = np.pad(my, (0, pad)).reshape(-1, Wd)
                r = cv2.remap(self.mips[kk], mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
                res[m] += r.reshape(-1, self.ch)[:N].astype(np.float32)*w[:, None]
        res /= self.scale
        out[sel] = res if self.ch > 1 else res[:, 0]
        return out

def cloud_domes(a, px):
    """real cloud mask -> dome height above the flat base (m): a cumulus of radius r rises ~0.75 r
    (h = 0.75 sqrt(r^2-(r-e)^2), e = distance to the cloud edge, r = the cloud's own radius)"""
    m = (a > 0.22).astype(np.uint8)
    e = cv2.distanceTransform(m, cv2.DIST_L2, 5).astype(np.float32)*px
    r = cv2.dilate(e, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (41, 41)))
    h = 0.75*np.sqrt(np.clip(r*r-(r-e)**2, 0, None))
    h = np.minimum(h, DOME_MAX)*np.clip(a/0.45, 0, 1)
    return cv2.GaussianBlur(h, (0, 0), 0.8)

COARSER = {"L0": "LG", "L1": "L0", "LM": "L1", "L2": "LM"}
CORR = {}                     # name -> (log colour correction map (n, n, 3), half, px of the coarser level)
def _corr_at(name, x, y):
    lc, half, _ = CORR[name]; n = lc.shape[0]
    from scipy.ndimage import map_coordinates
    rr = (half-y)/(2*half)*n-0.5; cc = (x+half)/(2*half)*n-0.5
    return np.stack([map_coordinates(lc[..., c], [rr, cc], order=1, mode="nearest") for c in range(3)], -1)

def blob(x, y, half, r0, r1, round_=False):
    """raw v3: an organic border instead of the square: a rounded square (superellipse) or a circle, with a slow
    irregular wobble, smoothstep from 1 (inside r0) to 0 (beyond r1); always 0 at the data's real edge"""
    u, v = x/half, y/half
    r = np.hypot(u, v) if round_ else (np.abs(u)**4+np.abs(v)**4)**0.25
    wob = (0.055*np.sin(2*np.pi*u/0.55+1.3)*np.sin(2*np.pi*v/0.47+0.4)+0.035*np.sin(2*np.pi*(u+v)/0.31+2.1)
           +0.03*np.sin(2*np.pi*(u-0.6*v)/0.23+0.7))
    r = r*(1+wob)
    k = np.clip((r1-r)/(r1-r0), 0, 1); k = k*k*(3-2*k)
    return np.minimum(k, np.clip((1-np.maximum(np.abs(u), np.abs(v)))/0.03, 0, 1)).astype(np.float32)

def level_blob(name, x, y, half, inner=0.0):
    if name == "L2": return blob(x, y, half, 0.50-inner, 0.92, round_=True)
    return blob(x, y, half, 0.55-inner, 0.96)

def _interior(name, x, y, half):
    """0 at the level's border -> 1 well inside (where it no longer meets the coarser level)"""
    return level_blob(name, x, y, half, inner=0.2)

def level_rgb(L, name, x, y, fp, m, bias=-0.5):
    """raw v2: one coherent globe. A finer level (Belitung LM, the L1/L2 squares) takes the large-scale colour of
    the globe seen from afar (matched through the chain LG <- L0 <- L1 <- LM <- L2) and fades to its own true
    colours only when the camera is close (footprint 300 -> 25 m); toward its border its detail also fades to the
    coarser level's resolution. So no square shows, in colour or in sharpness."""
    lv = L[name]
    if name not in CORR:
        return lv["rgb"].sample(x, y, fp, mask=m, bias=bias)
    xs, ys, fs = x[m], y[m], fp[m]
    e = _interior(name, xs, ys, lv["half"])
    cpx = CORR[name][2]
    fmin = np.exp((1-e)*np.log(cpx)+e*np.log(lv["px"]))
    # open water: its fine texture (waves, glint) only exists inside the finer square, so from afar it is limited
    # to the coarser level's resolution everywhere and comes back only close up (footprint 150 -> 25 m)
    if "land" in lv:
        wat = 1-np.clip(lv["land"].sample(xs, ys, np.maximum(fs, cpx)), 0, 1)
        c = np.clip((np.log2(150.0)-np.log2(np.maximum(fs, 1e-3)))/(np.log2(150.0)-np.log2(25.0)), 0, 1)
        fw = np.exp((1-c)*np.log(cpx)+c*np.log(lv["px"]))
        fmin = np.maximum(fmin, wat*fw+(1-wat)*lv["px"])
    fpe = fp.copy(); fpe[m] = np.maximum(fs, fmin)
    out = lv["rgb"].sample(x, y, fpe, mask=m, bias=bias)
    kf = np.clip((np.log2(np.maximum(fs, 1e-3))-np.log2(25.0))/(np.log2(300.0)-np.log2(25.0)), 0, 1)
    k = np.maximum(kf, 1-e)
    out[m] *= np.exp(_corr_at(name, xs, ys)*k[:, None])
    return out

def harmonize(name, rgb, half, px, L):
    """raw v2: store (do not bake) the full large-scale colour correction of this level toward the coarser level's
    effective (already corrected) appearance; applied at render time by level_rgb"""
    cn = COARSER.get(name)
    rgb = rgb.astype(np.float32, copy=False)
    if cn not in L: return rgb
    n = 192; g = ((np.arange(n)+0.5)/n*2-1)*half
    X, Y = np.meshgrid(g, -g)
    c = L[cn]["rgb"].sample(X, Y, np.full(X.shape, 2*half/n, np.float32))
    if cn in CORR: c = c*np.exp(_corr_at(cn, X.ravel(), Y.ravel()).reshape(n, n, 3))
    f = cv2.resize(rgb, (n, n), interpolation=cv2.INTER_AREA)
    lc = np.log(np.maximum(c, 2e-3))-np.log(np.maximum(f, 2e-3))
    sig = float(np.clip(5000/(2*half/n), 2, 12))
    lc = np.clip(cv2.GaussianBlur(lc.astype(np.float32), (0, 0), sig), -0.6, 0.6)
    CORR[name] = (lc, half, L[cn]["px"])
    print("harmonize", name, "to", cn, "mean step %.1f %%" % (100*float(np.abs(np.expm1(lc)).mean())), flush=True)
    return rgb

LEVEL_FILES = {"LG": "LG_tex.npy", "L0": "L0_tex.npy", "L1": "L1_tex.npy", "LM": "LM_tex.npy", "L2": "L2_comp.npy"}
RGB_SCALE = 65535/0.8

def load_levels(names=("LG", "L0", "L1", "LM", "L2"), clouds=True, relief=True):
    L = {}
    for name, half, px in LEVELS:
        if name not in names or not os.path.exists(D(LEVEL_FILES[name])): continue
        a = np.load(D(LEVEL_FILES[name]), mmap_mode="r")
        rgb = harmonize(name, np.array(a[:3]).transpose(1, 2, 0), half, px, L)
        lv = {"half": half, "px": px, "rgb": Tex(rgb, half, px, RGB_SCALE)}; del rgb
        if name in ("L0", "L1", "LM", "L2"):
            lv["land"] = Tex((np.array(a[3]) > 0.5).astype(np.float32), half, px, 65535.0)
        if clouds and os.path.exists(D(f"{name}_clouds.npy")):
            al = np.load(D(f"{name}_clouds.npy")).astype(np.float32)
            if name in ("LM", "L1"):
                # keep the cumulus over the sea; over land, seen from far up, they read as dirt on Belitung
                # (removing clouds is allowed, adding never): soft 1 km margin from the coast
                landm = (np.array(a[3]) > 0.5).astype(np.uint8)
                rad = max(1, int(round(1000/px)))
                landm = cv2.dilate(landm, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*rad+1, 2*rad+1)))
                al *= 1-cv2.GaussianBlur(landm.astype(np.float32), (0, 0), max(1.0, rad/2))
            lv["alpha"] = Tex(al, half, px, 65535.0)
            lv["dome"] = Tex(cloud_domes(al, px), half, px, 65535.0/1000)
        dem = {"L2": "L2_cop.npy", "LM": "LM_cop.npy"}.get(name)
        if relief and dem and os.path.exists(D(dem)):
            h = np.load(D(dem)).astype(np.float32)
            land = np.array(a[3]) > 0.5
            h = np.where(cv2.GaussianBlur(land.astype(np.float32), (0, 0), 1.5) > 0.5, np.clip(h, 0, None), 0)
            lv["dem"] = Tex(cv2.GaussianBlur(h, (0, 0), 0.8), half, px, 100.0)
        if clouds and name in ("LG", "L0") and os.path.exists(D(f"{name}_hcloud.npy")):
            lv["hcl"] = Tex(np.load(D(f"{name}_hcloud.npy")).astype(np.float32), half, px, 65535.0)
            lv["htop"] = Tex(np.load(D(f"{name}_htop.npy")), half, px, 65535.0/16000)
            if os.path.exists(D(f"{name}_hbright.npy")):
                lv["hbr"] = Tex(np.load(D(f"{name}_hbright.npy")).astype(np.float32), half, px, 65535.0/1.5)
        if name == "L2" and os.path.exists(D("L2_light.npy")):
            lv["light"] = Tex(np.load(D("L2_light.npy")), half, px, 65535.0)
        L[name] = lv
        print("level", name, "loaded", {k: v.mips[0].shape for k, v in lv.items() if isinstance(v, Tex)}, flush=True)
    return L

ORDER = ["L2", "LM", "L1", "L0", "LG"]
# how far (in footprint / pixel size) a level is kept before the next coarser one takes over. v8 used 2.6
# everywhere, so above ~40 m per pixel Belitung came from the 100 m class map (L1). LM is real Sentinel-2:
# keep it, mipmapped, up to ~500 m per pixel.
LEVEL_REACH = {"LM": 32.0}
def level_weights(L, x, y, fp):
    """per-pixel weight of each level: finest that resolves the footprint, soft blends in between"""
    rem = np.ones(x.shape, np.float32); W = {}
    last = [n for n in ORDER if n in L][-1]
    for name in ORDER:
        if name not in L: continue
        lv = L[name]
        if name == last:
            W[name] = rem; break
        ew = level_blob(name, x, y, lv["half"])          # raw v3: organic, wide, never a straight line
        # raw: no footprint threshold any more (it popped at ~14 s): every pixel samples the finest level that
        # covers it, mip-mapped trilinearly; levels only meet spatially, at their feathered borders, where the
        # finer level's colours are matched to the coarser one at load time (harmonize)
        w = ew
        W[name] = w*rem; rem = rem*(1-w)
    return W

def sample_field(L, key, x, y, fp, W, bias=0.0):
    """blend a scalar field (dem / alpha / dome) over the levels that have it, using the level weights"""
    out = np.zeros(x.shape, np.float32); ws = np.zeros(x.shape, np.float32)
    for name, w in W.items():
        lv = L[name]
        if key not in lv: continue
        m = w > 1e-4
        if m.any():
            out += lv[key].sample(x, y, fp, mask=m, bias=bias)*w; ws += w
    return out, ws

def to_xy(P):
    r = np.linalg.norm(P, axis=-1)
    lat = np.degrees(np.arcsin(np.clip(P[..., 2]/r, -1, 1))); lon = np.degrees(np.arctan2(P[..., 1], P[..., 0]))
    x, y = aeqd(lat, lon)
    return x.astype(np.float64), y.astype(np.float64), r-R_E

# ------------------------------------------------------------------ atmosphere
def sun_dir_ecef():
    from geo import LAT0, LON0
    e, n, u = enu_basis(LAT0, LON0)
    a, el = math.radians(SUN_AZ), math.radians(SUN_EL)
    return math.sin(a)*math.cos(el)*e+math.cos(a)*math.cos(el)*n+math.sin(el)*u
SUN = sun_dir_ecef()

def optical_depth(h0, h1, mu, H):
    """column of an exponential atmosphere (scale height H) between heights h0 (camera) and h1 along a
    ray whose cosine to the local vertical is mu; grazing rays capped by the Chapman horizontal factor"""
    mu_min = math.sqrt(2*H/(math.pi*R_E))
    m = np.sqrt(mu*mu+mu_min*mu_min)
    a, b = np.minimum(h0, h1), np.maximum(h0, h1)
    return H*(np.exp(-np.clip(a, 0, None)/H)-np.exp(-np.clip(b, 0, None)/H))/m

def phase_mie(c, g=0.72):
    return (1-g*g)/(4*np.pi*np.power(np.maximum(1+g*g-2*g*c, 1e-4), 1.5))*4*np.pi

def atmosphere(col, d, h_cam, h_hit, mu, dist_inf, warm, haze=1.0):
    """apply transmittance + in-scattering. col: surface radiance (reflectance units).
    haze < 1 thins the air on the ground only (v9: the descent over Belitung read as a blue-violet veil)"""
    odr = optical_depth(h_cam, h_hit, mu, HR)*haze; odm = optical_depth(h_cam, h_hit, mu, HM)*haze
    Tr = np.exp(-(odr[..., None]*BR))
    Tm = np.exp(-(odm*BM))[..., None]
    c = (d@SUN).astype(np.float32)
    pm = phase_mie(c)[..., None]
    pr = (0.75*(1+c*c))[..., None]
    skyR = SKY_R*np.array([1.0+0.06*warm, 1.0+0.02*warm, 1.0-0.05*warm], np.float32)
    skyM = SKY_M*np.array([1.0+0.10*warm, 1.0+0.04*warm, 1.0-0.08*warm], np.float32)
    ins = (1-Tr)*skyR*pr+(1-Tm)*skyM*(0.35+0.18*pm)
    return col*Tr*Tm+ins

# ------------------------------------------------------------------ clouds (2.5D domes over flat bases)
def sphere_hits(C, d, Rs):
    b = d@C; disc = b*b-(C@C-Rs*Rs)
    s = np.sqrt(np.maximum(disc, 0))
    return disc > 0, -b-s, -b+s

def clouds(L, C, d, cam, fp_unit, t, tt_ground, hit_ground, Wfun, n_steps=28):
    """returns cloud colour (linear, before atmosphere), coverage, distance to the cloud hit"""
    Rb, Rt = R_E+CLOUD_BASE, R_E+CLOUD_BASE+DOME_MAX
    okt, t0, _ = sphere_hits(C, d, Rt)
    okb, t1, _ = sphere_hits(C, d, Rb)
    t1 = np.where(okb, t1, np.where(hit_ground, tt_ground, t0+20000))
    cand = okt & (t0 > 0) & (cam.alt > CLOUD_BASE+DOME_MAX)
    cov = np.zeros(d.shape[:2], np.float32); ccol = np.zeros(d.shape, np.float32); cdist = np.zeros(d.shape[:2], np.float32)
    if not cand.any(): return ccol, cov, cdist
    # far clouds (smaller than a few pixels): a soft layer averaged over the pixel footprint, like a real sensor
    okm, tm, _ = sphere_hits(C, d, R_E+CLOUD_BASE+120)
    fpm = np.maximum(fp_unit*np.where(okm, tm, 0), 1.0)
    wd_all = np.clip((fpm-16.0)/22.0, 0, 1)*cand*okm*(tm > 0)     # raw: domes only where they are sharp (< ~30 m/px)
    if (wd_all > 0).any():
        jf = np.nonzero(wd_all > 0)
        Pm = C+d[jf]*tm[jf][:, None]
        xm_, ym_, _ = to_xy(Pm)
        xm_ += -WIND[0]*t; ym_ += -WIND[1]*t
        Wf = Wfun(xm_, ym_, fpm[jf])
        # v9: sampled at the pixel footprint (v8: x4 and a mip bias, which smeared the real cumulus into veils)
        af, _ = sample_field(L, "alpha", xm_, ym_, fpm[jf]*1.8, Wf, bias=1.0)
        k_alt = float(np.clip(1-(cam.alt-20000)/90000, 0.10, 1.0))
        # raw: cumulus smaller than the pixel cannot be drawn credibly (they read as snow): a faint soft veil only
        k_far = 0.30*np.clip(1-(fpm[jf]-16.0)/240.0, 0.15, 1.0)
        cf = np.clip(af*0.85*k_alt*k_far, 0, 1)
        cov[jf] = cf*wd_all[jf]; cdist[jf] = tm[jf]
        ccol[jf] = np.array([0.56, 0.575, 0.60], np.float32)*(0.90+0.10*cf[:, None])
    near = cand & (wd_all < 1)
    if not near.any(): return ccol, cov, cdist
    cand = near
    idx = np.nonzero(cand)
    dd = d[idx]; a0 = t0[idx]; a1 = t1[idx]
    P0 = C+dd*a0[:, None]; P1 = C+dd*a1[:, None]
    x0, y0, h0 = to_xy(P0); x1, y1, h1 = to_xy(P1)
    wx, wy = -WIND[0]*t, -WIND[1]*t            # sample the cloud field where it was at t=0
    x0 += wx; x1 += wx; y0 += wy; y1 += wy
    fpc = np.maximum(fp_unit[idx]*(a0+a1)*0.5, 8.0)
    # quick reject: no cloud anywhere near this segment (blurred field at the segment scale)
    seg = np.hypot(x1-x0, y1-y0)
    xm, ym = (x0+x1)/2, (y0+y1)/2
    Wm = Wfun(xm, ym, np.maximum(fpc, seg))
    amax, _ = sample_field(L, "dome", xm, ym, np.maximum(fpc, seg*0.7), Wm, bias=1.0)
    live = amax > 0.5
    if not live.any(): return ccol, cov, cdist
    sel = np.nonzero(live)[0]
    x0, y0, h0, x1, y1, h1, fpc, a0, a1 = (v[sel] for v in (x0, y0, h0, x1, y1, h1, fpc, a0, a1))
    Wl = Wfun(xm[sel], ym[sel], fpc)
    hit = np.zeros(sel.size, bool); s_hit = np.ones(sel.size, np.float32)
    prev = np.zeros(sel.size, np.float32)
    for k in range(1, n_steps+1):
        s = k/n_steps
        xs, ys, hs = x0+(x1-x0)*s, y0+(y1-y0)*s, h0+(h1-h0)*s
        todo = ~hit
        if not todo.any(): break
        dome = np.zeros(sel.size, np.float32)
        dome_t, _ = sample_field(L, "dome", xs[todo], ys[todo], fpc[todo], {n: w[todo] for n, w in Wl.items()})
        dome[todo] = dome_t
        inside = todo & (hs-CLOUD_BASE < dome) & (dome > 2.0)
        # refine the crossing linearly between the previous and this step
        gap_prev = prev; gap_now = (hs-CLOUD_BASE)-dome
        frac = np.where(inside, np.clip(gap_prev/np.maximum(gap_prev-gap_now, 1e-3), 0, 1), 1)
        s_hit = np.where(inside, (k-1+frac)/n_steps, s_hit)
        hit |= inside; prev = np.where(todo, gap_now, prev)
    if not hit.any(): return ccol, cov, cdist
    hi = np.nonzero(hit)[0]; s = s_hit[hi]
    xs, ys, hs = x0[hi]+(x1[hi]-x0[hi])*s, y0[hi]+(y1[hi]-y0[hi])*s, h0[hi]+(h1[hi]-h0[hi])*s
    fph = fpc[hi]; Wh = {n: w[hi] for n, w in Wl.items()}
    e = np.maximum(fph, 12.0)
    hx1, _ = sample_field(L, "dome", xs+e, ys, fph, Wh); hx0, _ = sample_field(L, "dome", xs-e, ys, fph, Wh)
    hy1, _ = sample_field(L, "dome", xs, ys+e, fph, Wh); hy0, _ = sample_field(L, "dome", xs, ys-e, fph, Wh)
    al, _ = sample_field(L, "alpha", xs, ys, fph, Wh)
    nx, ny = -(hx1-hx0)/(2*e), -(hy1-hy0)/(2*e)
    nrm = np.stack([nx, ny, np.ones_like(nx)], -1); nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
    a, el = math.radians(SUN_AZ), math.radians(SUN_EL)
    sl = np.array([math.sin(a)*math.cos(el), math.cos(a)*math.cos(el), math.sin(el)], np.float32)
    ndl = nrm@sl
    # sunlit tops, cool shadowed flanks, darker towards the flat base; thin edges let light through
    hrel = np.clip((hs-CLOUD_BASE)/np.maximum(DOME_MAX*0.6, 1), 0, 1)
    # v9: more modelling: sunlit tops, grey-blue flanks in their own shade, darker flat bases
    sunlit = np.clip((ndl+0.05)/1.05, 0, 1)**1.6
    base_dark = 0.36+0.64*np.sqrt(hrel)
    sun_part = 0.60*sunlit*base_dark
    amb = (0.065+0.075*hrel)[:, None]*np.array([0.80, 0.90, 1.10], np.float32)     # sky light in the shade: cool
    rgb = (sun_part[:, None]*np.array([1.0, 0.985, 0.95], np.float32)+amb).astype(np.float32)
    edge = np.clip(al/0.80, 0, 1)
    cv = (edge**1.4).astype(np.float32)*0.96                                         # v9: soft translucent rim
    rgb = rgb*(0.85+0.15*cv[:, None])                                               # thin fringes are greyer
    ii = (idx[0][sel[hi]], idx[1][sel[hi]])
    wn = 1-wd_all[ii]                                  # near-cloud share of this pixel
    ccol[ii] = ccol[ii]*(1-wn[:, None])+rgb*wn[:, None]
    cov[ii] = cov[ii]*(1-wn)+cv*wn; cdist[ii] = (a0[hi]+(a1[hi]-a0[hi])*s)
    return ccol, cov, cdist

def hi_fields(L, x, y, fp, bright=False):
    """Himawari opacity and cloud-top height (and, with bright=True, measured brightness): L0 inside its
    extent (feathered), LG outside"""
    out_a = np.zeros(x.shape, np.float32); out_h = np.zeros(x.shape, np.float32); out_b = np.zeros(x.shape, np.float32)
    if "LG" not in L or "hcl" not in L["LG"]: return (out_a, out_h, out_b) if bright else (out_a, out_h)
    w0 = L["L0"]["rgb"].edge(x, y, 0.1) if "L0" in L and "hcl" in L["L0"] else np.zeros(x.shape, np.float32)
    for name, w in (("L0", w0), ("LG", 1-w0)):
        m = w > 1e-4
        if m.any():
            out_a += L[name]["hcl"].sample(x, y, np.maximum(fp, 1.6*L[name]["px"]), mask=m, bias=1.3)*w
            out_h += L[name]["htop"].sample(x, y, np.maximum(fp, 1.6*L[name]["px"]), mask=m, bias=0.6)*w
            if bright and "hbr" in L[name]:
                out_b += L[name]["hbr"].sample(x, y, np.maximum(fp, 1.2*L[name]["px"]), mask=m, bias=0.3)*w
    # near Belitung the Sentinel-2 cumulus (10-100 m) take over: the 2 km field fades out there
    r = np.hypot(x, y)
    out_a *= np.clip((r-140000)/90000, 0, 1)
    return (out_a, out_h, out_b) if bright else (out_a, out_h)

def hi_clouds(L, C, d, cam, pix_ang):
    """real clouds of 29-07-2019 03:20 UTC (Himawari-8) at their real top height: colour, coverage, distance"""
    H0 = 6000.0
    ok, t0, _ = sphere_hits(C, d, R_E+H0)
    ok &= t0 > 0
    cov = np.zeros(d.shape[:2], np.float32); col = np.zeros(d.shape, np.float32); dist = np.zeros(d.shape[:2], np.float32)
    if not ok.any() or "LG" not in L or "hcl" not in L["LG"]: return col, cov, dist
    idx = np.nonzero(ok); dd = d[idx]; tt = t0[idx]
    for _ in range(2):                                   # fixed point: hit the sphere at the cloud's own top
        P = C+dd*tt[:, None]; x, y, _ = to_xy(P)
        fp = np.maximum(tt*pix_ang, 500.0)
        a, h = hi_fields(L, x, y, fp)
        hh = np.where(a > 0.02, np.clip(h, 800, 15000), H0)
        okk, tn, _ = sphere_hits(C, dd, R_E+hh)
        tt = np.where(okk & (tn > 0), tn, tt)
    P = C+dd*tt[:, None]; x, y, _ = to_xy(P)
    fp = np.maximum(tt*pix_ang, 500.0)
    a, h, br = hi_fields(L, x, y, fp, bright=True)
    e = np.maximum(fp, 2000.0)
    _, hx1 = hi_fields(L, x+e, y, fp); _, hx0 = hi_fields(L, x-e, y, fp)
    _, hy1 = hi_fields(L, x, y+e, fp); _, hy0 = hi_fields(L, x, y-e, fp)
    nx, ny = -(hx1-hx0)/(2*e)*3.0, -(hy1-hy0)/(2*e)*3.0      # tops relief, gently exaggerated for shading only
    n = np.stack([nx, ny, np.ones_like(nx)], -1); n /= np.linalg.norm(n, axis=-1, keepdims=True)
    az, el = math.radians(SUN_AZ), math.radians(SUN_EL)
    sl = np.array([math.sin(az)*math.cos(el), math.cos(az)*math.cos(el), math.sin(el)], np.float32)
    lit = np.clip((n@sl+0.2)/1.2, 0, 1)
    # v9: the satellite's own measurement of each cloud (bright sunlit cores, grey thin parts and shaded
    # flanks), taken at the same minute under the same sun, carries the real volume. A little of the
    # top-height relief keeps the shading alive at sub-kilometre scale. Shade is cooler (sky light).
    meas = np.clip(br, 0.15, 1.1)
    val = 0.80*(0.62*meas)+0.20*(0.30+0.30*lit)
    cool = np.clip((0.62-meas)/0.35, 0, 1)
    rgb = np.stack([val*(1-0.035*cool), val*(1+0.0*cool), val*(1+0.06*cool)], -1).astype(np.float32)
    # soft physical edges: thin cloud is translucent, no smoothstep cliff
    cv_ = 0.62*np.clip((a-0.04)/0.90, 0, 1)**1.35      # raw: lighter and softer (no flat white patches)
    cov[idx] = cv_; col[idx] = rgb; dist[idx] = tt
    return col, cov, dist

def hi_cloud_shadow(L, x, y, fp):
    """their shadows on the ground, displaced by the real top height under the real sun"""
    a0, h0 = hi_fields(L, x, y, np.maximum(fp, 1000.0))
    off = np.clip(h0, 800, 15000)/math.tan(math.radians(SUN_EL))
    sx, sy = off*math.sin(math.radians(SUN_AZ)), off*math.cos(math.radians(SUN_AZ))
    a, _ = hi_fields(L, x+sx, y+sy, np.maximum(fp, 1000.0))
    return np.clip(a, 0, 1)

def cloud_shadow(L, x, y, fp, t, W):
    off = (CLOUD_BASE+150)/math.tan(math.radians(SUN_EL))
    sx, sy = off*math.sin(math.radians(SUN_AZ)), off*math.cos(math.radians(SUN_AZ))
    a, ws = sample_field(L, "alpha", x+sx-WIND[0]*t, y+sy-WIND[1]*t, np.maximum(fp, 25.0), W, bias=0.8)
    return np.clip(a, 0, 1)

# ------------------------------------------------------------------ tone (display RAW plate)
LOOK = dict(exposure=2.55, saturation=0.92, contrast=0.36, black=0.04)
def tone(x, look=LOOK):
    x = x*look["exposure"]
    lum = (x*np.array([0.2126, 0.7152, 0.0722], np.float32)).sum(-1, keepdims=True)
    x = np.maximum(lum+(x-lum)*look["saturation"], 0)
    y = R5.filmic(x)**(1/2.2)
    y = np.clip((y-look["black"])/(1-look["black"]), 0, 1)
    c = look["contrast"]
    return y*(1-c)+(y*y*(3-2*y))*c

def space_sky(d, C):
    """v9: the limb seen from orbit, physical: the in-scatter of the column a ray grazes at its tangent height
    (Chapman grazing column ~ exp(-h/H) sqrt(2 pi R H)), so the atmosphere is a thin layered rim, not a wide halo:
    white-cyan where the column is thick, deep blue above, a faint violet (ozone absorption) higher up; dimmer
    where the tangent point is in shadow. The black is neutral."""
    b = d@C
    rmin = np.sqrt(np.maximum(C@C-b*b, 0)); h = np.where(b < 0, rmin-R_E, np.linalg.norm(C)-R_E)
    h = np.maximum(h, 0).astype(np.float32)
    g = math.sqrt(2*math.pi*R_E)
    odR = (np.exp(-h/HR)*math.sqrt(HR)*g)[..., None]*BR
    odM = (np.exp(-h/HM)*math.sqrt(HM)*g*BM)[..., None]
    Pt = C+d*np.where(b < 0, -b, 0)[..., None]
    nt = Pt/np.linalg.norm(Pt, axis=-1, keepdims=True)
    lit = np.clip((nt@SUN+0.10)/0.30, 0, 1).astype(np.float32)[..., None]
    c = (d@SUN).astype(np.float32)
    pr = (0.75*(1+c*c))[..., None]; pm = phase_mie(c)[..., None]
    ins = (1-np.exp(-odR))*SKY_R*pr*LIMB_GAIN+(1-np.exp(-odM))*SKY_M*(0.35+0.18*pm)*LIMB_GAIN
    w = (0.22*np.exp(-((h-38000.0)/14000.0)**2))[..., None]
    lum = (ins*np.array([0.2126, 0.7152, 0.0722], np.float32)).sum(-1, keepdims=True)
    ins = ins*(1-w)+lum*np.array([0.62, 0.48, 1.05], np.float32)*w
    return (BLACK+ins*lit).astype(np.float32)

LIMB_GAIN = 3.5
SKY_FLOOR = np.array([0x0B, 0x12, 0x22], np.float32)/255
BLACK = np.array([0.0011, 0.0011, 0.0013], np.float32)

# ------------------------------------------------------------------ the real stars (Yale Bright Star Catalogue)
_STARS = None
def _stars():
    global _STARS
    if _STARS is None:
        a = np.array(json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "stars_bsc_mag45.json")))["stars"], np.float64)
        a = a[a[:, 2] < 4.0]
        # J2000 RA -> Earth-fixed longitude at 2019-07-29 03:20 UTC (Greenwich mean sidereal time)
        D = 2458693.6388889-2451545.0
        gmst = (280.46061837+360.98564736629*D) % 360.0
        lon = np.radians(a[:, 0]-gmst); dec = np.radians(a[:, 1])
        v = np.stack([np.cos(dec)*np.cos(lon), np.cos(dec)*np.sin(lon), np.sin(dec)], -1)
        bv = a[:, 3]
        col = np.where(bv[:, None] < 0.3, [0.90, 0.94, 1.0], np.where(bv[:, None] < 1.0, [1.0, 0.98, 0.94], [1.0, 0.90, 0.80]))
        col = 0.15*col+0.85                               # saturation <= 15 %
        # plate values: after the grade's toe and the motion blur the brightest end at ~7 % of white, mag 4 at ~2 %
        bright = 0.66*10**(-0.4*0.35*np.clip(a[:, 2], -1.5, 4.0))
        _STARS = (v, col.astype(np.float32), bright.astype(np.float32))
    return _STARS

def add_stars(img, t, W, H):
    """faint real stars in the black, fixed in the sky; they fade together 1.2 -> 2.2 s as the exposure adapts"""
    k_t = 1.0                                         # raw: the same discreet real stars all through the video
    cam = cam_at(t, W, H)
    v, col, br = _stars()
    P = cam.pos+v*1e13
    p, z = cam.project(P)
    b = v@cam.pos; disc = b*b-(cam.pos@cam.pos-R_E**2)
    ok = (z > 0) & ~((disc > 0) & (b < 0)) & (p[:, 0] > -3) & (p[:, 0] < W+3) & (p[:, 1] > -3) & (p[:, 1] < H+3)
    s = 0.75*min(W, H)/1080; r = int(math.ceil(3*s))+1
    for (x, y), c, a in zip(p[ok], col[ok], br[ok]):
        ix, iy = int(round(x)), int(round(y))
        x0, x1, y0, y1 = max(ix-r, 0), min(ix+r+1, W), max(iy-r, 0), min(iy+r+1, H)
        if x1 <= x0 or y1 <= y0: continue
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        gk = np.exp(-((xx-x)**2+(yy-y)**2)/(2*s*s)); gk /= max(gk.max(), 1e-6)
        patch = img[y0:y1, x0:x1]
        dark = np.clip((0.20-patch.mean(-1))/0.08, 0, 1)        # only in the black, never over the limb
        img[y0:y1, x0:x1] = patch+(gk*dark*a*k_t)[..., None]*c
    return img

# ------------------------------------------------------------------ surface: tin mines, sand, reef flats
KNEE, KNEE_SLOPE = 0.13, 0.50
GLINT = 0.005
def bright_knee(col, landw=None):
    """soft shoulder on high surface reflectance (bare sand, tin mines, reef flats): hue kept, a touch warmer.
    On land the shoulder starts lower and is firmer (tin mines, bare ground). Nothing is removed: the mines
    stay where they are, they just stop shouting."""
    lum = (col*np.array([0.2126, 0.7152, 0.0722], np.float32)).sum(-1)
    kn = KNEE if landw is None else KNEE-0.055*landw
    sl = KNEE_SLOPE if landw is None else KNEE_SLOPE-0.18*landw
    over = np.maximum(lum-kn, 0)
    new = np.where(lum > kn, kn+over*sl/(1+over*2.0), lum)
    k = (new/np.maximum(lum, 1e-5))[..., None]
    w = np.clip(over/0.08, 0, 1)[..., None]
    warm = np.array([1.015, 1.0, 0.975], np.float32)
    return col*k*(1-w+w*warm)

# ------------------------------------------------------------------ one frame
def render_frame(t, L, W, H, ss=1.25, cam=None, want_matte=False, stats=None):
    Ws, Hs = int(round(W*ss)), int(round(H*ss))
    cam = cam or cam_at(t, Ws, Hs)
    t_0 = time.time()
    d = cam.rays().astype(np.float64); C = cam.pos
    b = d@C; cc = C@C-R_E**2; disc = b*b-cc
    hit = (disc > 0) & (b < 0)                         # (the intro looks away from the Earth: never hit behind)
    tt = np.where(hit, -b-np.sqrt(np.maximum(disc, 0)), 0)
    P = C+d*tt[..., None]
    x, y, _ = to_xy(P)
    nrm = P/np.linalg.norm(P, axis=-1, keepdims=True)
    cosi = np.clip(-(d*nrm).sum(-1), 0.02, 1).astype(np.float32)
    pix_ang = 2*cam.tanv/cam.H
    fp = (tt*pix_ang/np.sqrt(cosi)).astype(np.float32)
    Wl = level_weights(L, x, y, fp)
    # relief: walk the hit back along the ray by the local height (3 fixed-point steps = parallax)
    hh = np.zeros(x.shape, np.float32)
    if cam.alt < 60000 and any("dem" in L[n] for n in Wl):
        hgt, _ = sample_field(L, "dem", x, y, fp, Wl)
        sel = (hgt > 0.5) & (fp < 120)
        if sel.any():
            idx = np.nonzero(sel)
            xs, ys, fs, cs, ts_ = x[idx], y[idx], fp[idx], cosi[idx], tt[idx]
            ds = d[idx]; Ws = {k: w[idx] for k, w in Wl.items()}
            h_ = hgt[idx]
            for _ in range(2):
                P2 = C+ds*(ts_-h_/cs)[:, None]
                xs, ys, _ = to_xy(P2)
                h_, _ = sample_field(L, "dem", xs, ys, fs, Ws)
            x = x.copy(); y = y.copy()
            x[idx], y[idx] = xs, ys; hh[idx] = h_
            tt = tt-hh/cosi
    col = np.zeros(x.shape+(3,), np.float32); wsum = np.zeros(x.shape, np.float32)
    for name, w in Wl.items():
        m = (w > 1e-4) & hit
        if m.any():
            col += level_rgb(L, name, x, y, fp, m)*w[..., None]; wsum += w
    col /= np.maximum(wsum, 1e-6)[..., None]
    landw, lws = sample_field(L, "land", x, y, fp, Wl)
    landw = np.where(lws > 1e-3, landw/np.maximum(lws, 1e-6), 0)
    # v9: open water seen from high up: its 15-100 m texture is wave and glint noise in the median, not features.
    # Filter it softer (mip bias +2) where the footprint is coarse; shallows and coasts keep their detail.
    wsoft = (1-np.clip(landw*3, 0, 1))*np.clip((fp-40.0)/80.0, 0, 1)
    if wsoft.max() > 0.02:
        lum0 = col@np.array([0.2126, 0.7152, 0.0722], np.float32)
        wsoft *= np.clip((0.075-lum0)/0.03, 0, 1)                    # deep (dark) water only
        if wsoft.max() > 0.02:
            c2 = np.zeros_like(col); ws2 = np.zeros(x.shape, np.float32)
            for name, w in Wl.items():
                m = (w > 1e-4) & hit & (wsoft > 0.01)
                if m.any():
                    c2 += level_rgb(L, name, x, y, fp, m, bias=2.2)*w[..., None]; ws2 += w*m
            c2 /= np.maximum(ws2, 1e-6)[..., None]
            col = col*(1-wsoft[..., None])+c2*wsoft[..., None]
    col = bright_knee(col, landw)
    # sun glint: the sun's specular reflection on open water (wind-roughened, ~10 deg wide), real geometry
    nrm32 = nrm.astype(np.float32); d32 = d.astype(np.float32)
    refl = d32-2*(d32*nrm32).sum(-1, keepdims=True)*nrm32
    cg = np.clip(refl@SUN.astype(np.float32), -1, 1)
    ang = np.degrees(np.arccos(cg))
    glint = np.exp(-(ang/16.0)**2)*(1-np.clip(landw, 0, 1))*hit
    if glint.max() > 1e-3:                         # v9: 0.032 -> 0.005, wider: no round blob on the lens
        col += (GLINT*glint)[..., None]*np.array([1.0, 0.97, 0.90], np.float32)
    t_tex = time.time()
    # Seliu in the light (matte), the rest a touch darker
    light = None
    if "L2" in L and "light" in L["L2"]:
        inside = (np.abs(x) < 31000) & (np.abs(y) < 31000)
        light = L["L2"]["light"].sample(x, y, fp, mask=inside)
        near_seliu = np.clip((30000-np.hypot(x, y))/30000, 0, 1)**0.5
    # cloud shadows on the ground
    if fp.min() < 3000:
        sh = cloud_shadow(L, x, y, fp, t, level_weights(L, x, y, fp/3.0))
        k_alt = float(np.clip(1-(cam.alt-25000)/120000, 0.25, 1.0))
        col *= (1-0.50*k_alt*sh)[..., None]
    # shadows of the high real clouds (orbit, region)
    if cam.alt > 40000 and "LG" in L and "hcl" in L["LG"]:
        shh = hi_cloud_shadow(L, x, y, fp)
        col *= (1-0.45*shh)[..., None]
    # atmosphere on the ground
    h_cam = cam.alt
    mu = cosi
    warm = TL.warmth(t)
    col = atmosphere(col, d.astype(np.float32), h_cam, hh, mu, None, warm, haze=TL.haze(t))
    # high real clouds (Himawari-8, same instant), seen through the air above and below them
    if cam.alt > 40000:
        hc, hcov, hd = hi_clouds(L, C, d, cam, pix_ang)
        if hcov.max() > 0:
            k_fade = float(np.clip((cam.alt-40000)/60000, 0, 1))
            mu_h = np.clip(np.abs((d*(C/np.linalg.norm(C))).sum(-1)), 0.02, 1).astype(np.float32)
            hc = atmosphere(hc, d.astype(np.float32), cam.alt, np.full(hcov.shape, 7000.0, np.float32), mu_h, None, TL.warmth(t))
            # v9: seen almost edge-on near the limb the 1-2 km cloud field streaks into lines: there the real
            # clouds sink into the haze (they are foreshortened below a pixel anyway)
            hcov = hcov*k_fade*hit*np.clip((cosi-0.05)/0.20, 0, 1)
            col = col*(1-hcov[..., None])+hc*hcov[..., None]
    # clouds
    t_cl = time.time()
    if fp.min() < 3000 and cam.alt < 400000:
        Wfun = lambda xx, yy, ff: level_weights(L, xx, yy, ff/3.0)     # clouds: always the finest cloud field
        ccol, cov, cdist = clouds(L, C, d, cam, (pix_ang/np.sqrt(cosi)).astype(np.float32), t, tt, hit, Wfun)
        if cov.max() > 0:
            # cloud tops seen through the air above them
            hc = np.full(cov.shape, CLOUD_BASE+200.0, np.float32)
            mu_c = np.clip(-(d.astype(np.float32)*nrm.astype(np.float32)).sum(-1), 0.02, 1)
            ccol = atmosphere(ccol, d.astype(np.float32), h_cam, hc, mu_c, None, warm, haze=TL.haze(t))
            col = col*(1-cov[..., None])+ccol*cov[..., None]
    t_cle = time.time()
    # Seliu in the light: +25 % on the island and its reef, -30 % around it (after the air, like a grade);
    # the lift is weighted toward mid-tones so the white sand ring does not bloom
    if light is not None and TL.glow(t) > 0:
        gl = TL.glow(t)
        lum = (col*np.array([0.2126, 0.7152, 0.0722], np.float32)).sum(-1)
        mid = np.clip(1-(lum-0.10)/0.25, 0.25, 1)
        up, down = (0.25, 0.30) if os.environ.get("SELIU_LOOK") != "warm" else (0.34, 0.38)
        k = 1+gl*(up*light*mid-down*(1-light)*near_seliu)
        col *= k[..., None]
    # beyond the limb / above the horizon
    if (~hit).any():
        dz = (d@(C/np.linalg.norm(C))).astype(np.float32)
        sky = atmosphere(np.zeros(d.shape, np.float32), d.astype(np.float32), h_cam, np.full(dz.shape, 1e6, np.float32), np.abs(dz), None, warm)
        if cam.alt > 60000:
            sp = space_sky(d, C).astype(np.float32)
            k_space = min(1.0, (cam.alt-60000)/200000)
            sky = sky*(1-k_space)+sp*k_space
        edge = np.clip((disc/(np.abs(disc).max()+1e-9))*4000, 0, 1)[..., None] if cam.alt > 60000 else hit[..., None].astype(np.float32)
        col = np.where(hit[..., None], col*edge+sky*(1-edge), sky)
    img = tone(col)
    if ss != 1: img = cv2.resize(img, (W, H), interpolation=cv2.INTER_AREA)
    if cam.alt > 600000:                                   # v9: lens diffusion from the real bright limb (<= 6 %)
        k = min(W, H)/1080
        sky_only = np.where(cv2.resize((~hit).astype(np.float32), (W, H), interpolation=cv2.INTER_AREA)[..., None] > 0.5, img, 0)
        src = np.clip(sky_only-0.08, 0, 1)
        small = cv2.resize(src, (W//4, H//4), interpolation=cv2.INTER_AREA)
        bl = 0.6*cv2.GaussianBlur(small, (0, 0), 3.0*k)+0.4*cv2.GaussianBlur(small, (0, 0), 9.0*k)
        bl = cv2.resize(bl, (W, H), interpolation=cv2.INTER_LINEAR)
        kd = float(np.clip((cam.alt-600000)/600000, 0, 1))
        img = 1-(1-img)*(1-np.clip(0.55*kd*bl, 0, 0.06))
    if (~hit).any():                                   # raw: deep blue-black space (~#0B1222), screened under the limb
        nh = cv2.resize((~hit).astype(np.float32), (W, H), interpolation=cv2.INTER_AREA)[..., None]
        img = 1-(1-img)*(1-SKY_FLOOR*nh)
    if cam.alt > 1000000: img = add_stars(img, t, W, H)
    matte = None
    if want_matte and light is not None:
        matte = cv2.resize(np.clip(light, 0, 1).astype(np.float32), (W, H), interpolation=cv2.INTER_AREA)
    if stats is not None:
        stats.update(tex=t_tex-t_0, clouds=t_cle-t_cl, total=time.time()-t_0, alt=cam.alt)
    return img, matte

# ------------------------------------------------------------------ motion blur from the real screen speed
def screen_speed(t, W, H, dt=1/TL.FPS):
    """median and max on-screen motion (px per frame) of a grid of ground points"""
    c0, c1 = cam_at(t, W, H), cam_at(t+dt, W, H)
    xs, ys = np.meshgrid(np.linspace(0.1, 0.9, 7)*W, np.linspace(0.15, 0.95, 5)*H)
    d = c0.rays()
    # cast the grid rays of camera 0 to the ground and reproject them with camera 1
    jj = np.clip(xs.astype(int), 0, W-1); ii = np.clip(ys.astype(int), 0, H-1)
    dd = d[ii, jj]; C = c0.pos
    b = dd@C; disc = b*b-(C@C-R_E**2); ok = disc > 0
    if not ok.any(): return 0.0, 0.0
    tt = -b[ok]-np.sqrt(disc[ok]); P = C+dd[ok]*tt[:, None]
    p0, _ = c0.project(P); p1, _ = c1.project(P)
    v = np.linalg.norm(p1-p0, axis=-1)
    return float(np.median(v)), float(v.max())

def flow_blur(img, t, W, H, shutter=0.5, taps=9):
    """motion blur from the real camera motion: every pixel is smeared along its own screen path during a
    180-degree shutter (ground points reprojected with the camera at t -/+ shutter/2 frames)"""
    dt = shutter/TL.FPS
    c = cam_at(t, W, H); c0, c1 = cam_at(t-dt/2, W, H), cam_at(t+dt/2, W, H)
    d = c.rays(); C = c.pos
    b = d@C; disc = b*b-(C@C-R_E**2)
    tt = np.where(disc > 0, -b-np.sqrt(np.maximum(disc, 0)), 1e8)
    P = C+d*tt[..., None]
    p0, _ = c0.project(P); p1, _ = c1.project(P)
    v = (p1-p0).astype(np.float32)
    mag = np.linalg.norm(v, axis=-1)
    if mag.max() < 0.02: return img                    # raw: no threshold (it switched off at ~23 s)
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    acc = np.zeros_like(img)
    for k in range(taps):
        f = k/(taps-1)-0.5
        acc += cv2.remap(img, xs+v[..., 0]*f, ys+v[..., 1]*f, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return acc/taps

def blur_offsets(t, W, H):
    """shutter 180 deg (1/50 s): enough sub-frames that each moves < ~1.5 px"""
    med, mx = screen_speed(t, W, H)
    n = int(np.clip(math.ceil(med*0.5/1.5), 1, 8))
    if n == 1: return [0.0]
    return list(np.linspace(-0.25, 0.25, n)/TL.FPS)

# ------------------------------------------------------------------ raw delivery
def sky_mask(t, W, H, ss=2):
    """1 where the pixel sees space (anti-aliased), from the same camera"""
    c = cam_at(t, W*ss, H*ss); d = c.rays(); C = c.pos
    b = d@C; disc = b*b-(C@C-R_E**2)
    m = ~((disc > 0) & (b < 0))
    return cv2.resize(m.astype(np.float32), (W, H), interpolation=cv2.INTER_AREA)

def gfx_rgba(draw_fn, W, H):
    """one graphic alone -> straight RGBA (difference matte: composited over black and over white)"""
    import motion_gfx_v9 as M
    cv = M.Canvas(W, H, "16x9"); draw_fn(cv)
    if not (cv.ink[..., 3] > 1e-4).any() and not (cv.glow > 1e-4).any(): return None
    b = cv.composite(np.zeros((H, W, 3), np.float32)); w = cv.composite(np.ones((H, W, 3), np.float32))
    a = np.clip(1-(w-b), 0, 1).max(-1)
    col = np.clip(b/np.maximum(a, 1e-4)[..., None], 0, 1)
    return np.dstack([col, a])

def raw_write(out, name, img, matte, t, W, H):
    import grade_v9 as G, motion_gfx_v9 as M
    for sub in ("flat", "grade", "json", "gfx_voli", "gfx_scia", "gfx_costa"): os.makedirs(os.path.join(out, sub), exist_ok=True)
    w16 = lambda p, x: cv2.imwrite(p, cv2.cvtColor((np.clip(x, 0, 1)*65535+0.5).astype(np.uint16), cv2.COLOR_RGB2BGR))
    w16(os.path.join(out, "flat", name+".png"), img)
    x = G.grade(img, max(t, 0.0), matte)
    m = sky_mask(t, W, H)[..., None]
    x = x*(1-m)+img*m                                  # space keeps the plate's #0B1222 and stars, the same all through
    w16(os.path.join(out, "grade", name+".png"), x)
    cam = cam_at(t, W, H)
    layers = {"gfx_voli": (lambda cv: (M.flight(cv, cam, M.ARC_SIN, t, *M.T["arc_sin"]), M.flight(cv, cam, M.ARC_CGK, t, *M.T["arc_cgk"]))) if 3.8 < t < 9.6 else None,
              "gfx_scia": lambda cv: M.wake(cv, cam, t), "gfx_costa": lambda cv: M.coast_light(cv, cam, t)}
    for k, fn in layers.items():
        if fn is None: continue
        r = gfx_rgba(fn, W, H)
        if r is not None:
            cv2.imwrite(os.path.join(out, k, name+".png"), cv2.cvtColor((r*255+0.5).astype(np.uint8), cv2.COLOR_RGBA2BGRA))

# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode"); ap.add_argument("out"); ap.add_argument("times", nargs="*", type=float)
    ap.add_argument("--w", type=int, default=1920); ap.add_argument("--h", type=int, default=1080)
    ap.add_argument("--ss", type=float, default=1.25)
    ap.add_argument("--from_", type=float, default=0); ap.add_argument("--to", type=float, default=TL.DURATION)
    ap.add_argument("--every", type=int, default=1); ap.add_argument("--shard", default="0/1")
    ap.add_argument("--noblur", action="store_true"); ap.add_argument("--final", action="store_true")
    ap.add_argument("--subframes", action="store_true", help="true multi-sample motion blur (slow)")
    ap.add_argument("--workers", type=int, default=1, help="forked workers sharing the textures")
    ap.add_argument("--clean", action="store_true", help="with --final: no graphics")
    ap.add_argument("--clean_dir", default=None, help="with --final: also write the no-text version here")
    ap.add_argument("--raw_out", default=None, help="raw delivery: flat/ and grade/ 16-bit, gfx layers RGBA, no fade")
    ap.add_argument("--raw_dir", default=None, help="with --final: also write the RAW plate (16-bit, no grade, no text, no grain) here")
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    L = load_levels()
    if a.mode == "stills": jobs = [(None, t) for t in a.times]
    else:
        n0, n1 = int(round(a.from_*TL.FPS)), int(round(a.to*TL.FPS))
        if a.raw_out:                  # raw: frame 0 is t = T_START
            T0 = getattr(TL, "T_START", 0.0); n0, n1 = int(round((a.from_-T0)*TL.FPS)), int(round((a.to-T0)*TL.FPS))
            jobs = [(f, T0+f/TL.FPS) for f in range(n0, n1, a.every)]
        else:
            jobs = [(f, f/TL.FPS) for f in range(n0, n1, a.every)]
    k, K = map(int, a.shard.split("/")); jobs = jobs[k::K]
    if a.workers > 1:
        # fork after loading: the textures are shared copy-on-write between the workers (memory ~ halved)
        import gc; gc.collect(); gc.freeze()
        kids = []
        for wk in range(1, a.workers):
            pid = os.fork()
            if pid == 0:
                jobs = jobs[wk::a.workers]; kids = None; break
            kids.append(pid)
        if kids is not None:
            jobs = jobs[0::a.workers]
    for f, t in jobs:
        name = f"t{t:06.2f}" if f is None else f"f{f:05d}"
        png = os.path.join(a.out, name+".png")
        if f is not None and os.path.exists(png): continue           # resume
        if a.raw_out and f is not None and (os.path.exists(os.path.join(a.raw_out, "json", name+".json"))): continue
        t0 = time.time()
        offs = blur_offsets(t, a.w, a.h) if a.subframes else [0.0]
        acc = None; st = {}
        for dt in offs:
            im, matte = render_frame(t+dt, L, a.w, a.h, a.ss, want_matte=True, stats=st)
            acc = im if acc is None else acc+im
        img = acc/len(offs)
        if not a.noblur and not a.subframes:
            img = flow_blur(img, t, a.w, a.h)
        cp = TL.camera(t)
        rec = {"t": t, "frame": f, "camera": dict(zip(["lat", "lon", "range_m", "heading", "tilt", "roll"], cp)), "vfov": TL.VFOV,
               "alt_m": st.get("alt"), "subframes": len(offs), "sec": round(time.time()-t0, 1), "timing": {k: round(v, 2) for k, v in st.items() if k != "alt"}}
        if a.raw_out:
            raw_write(a.raw_out, name, img, matte, t, a.w, a.h)
            json.dump(rec, open(os.path.join(a.raw_out, "json", name+".json"), "w"))
            print(name, f"alt={rec['alt_m']/1000:.1f}km sub={len(offs)} {rec['sec']}s", rec["timing"], flush=True)
            continue
        if a.final and a.raw_dir:
            os.makedirs(a.raw_dir, exist_ok=True)
            cv2.imwrite(os.path.join(a.raw_dir, name+".png"), cv2.cvtColor((np.clip(img, 0, 1)*65535+0.5).astype(np.uint16), cv2.COLOR_RGB2BGR))
        if a.final:
            import grade_v9 as G, motion_gfx_v9 as M
            x = G.grade(img, t, matte)
            seed = (f or int(t*1000))
            if a.clean_dir:
                os.makedirs(a.clean_dir, exist_ok=True)
                cv2.imwrite(os.path.join(a.clean_dir, name+".png"), cv2.cvtColor(G.finish(x*TL.fade(t), seed=seed), cv2.COLOR_RGB2BGR))
            if not a.clean:
                x = M.draw(x, t, cam_at(t, a.w, a.h), fmt=TL.FMT)
            x = x*TL.fade(t)
            out = G.finish(x, seed=seed)
            cv2.imwrite(png, cv2.cvtColor(out, cv2.COLOR_RGB2BGR))
        else:
            cv2.imwrite(png, cv2.cvtColor((np.clip(img, 0, 1)*65535+0.5).astype(np.uint16), cv2.COLOR_RGB2BGR))
            if matte is not None:
                cv2.imwrite(os.path.join(a.out, name+"_matte.png"), (np.clip(matte, 0, 1)*255+0.5).astype(np.uint8))
        json.dump(rec, open(os.path.join(a.out, name+".json"), "w"))
        print(name, f"alt={rec['alt_m']/1000:.1f}km sub={len(offs)} {rec['sec']}s", rec["timing"], flush=True)
    if a.workers > 1:
        if kids is None: os._exit(0)
        for pid in kids: os.waitpid(pid, 0)

if __name__ == "__main__":
    main()
