"""Seliu v8 renderer: one physical camera over the real, round Earth.

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
import timeline_v8 as TL

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
SKY_M = np.array([0.24, 0.235, 0.22], np.float32)

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
    return Camera(*p[:5], vfov=TL.VFOV, W=W, H=H, roll=p[5])

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

LEVEL_FILES = {"LG": "LG_tex.npy", "L0": "L0_tex.npy", "L1": "L1_tex.npy", "LM": "LM_tex.npy", "L2": "L2_comp.npy"}
RGB_SCALE = 65535/0.8

def load_levels(names=("LG", "L0", "L1", "LM", "L2"), clouds=True, relief=True):
    L = {}
    for name, half, px in LEVELS:
        if name not in names or not os.path.exists(D(LEVEL_FILES[name])): continue
        a = np.load(D(LEVEL_FILES[name]), mmap_mode="r")
        lv = {"half": half, "px": px, "rgb": Tex(np.array(a[:3]).transpose(1, 2, 0), half, px, RGB_SCALE)}
        if clouds and os.path.exists(D(f"{name}_clouds.npy")):
            al = np.load(D(f"{name}_clouds.npy")).astype(np.float32)
            if name == "L2":   # L2 holds only the hand-picked clean-plate clouds; the field comes from LM
                al *= 1.0
            lv["alpha"] = Tex(al, half, px, 65535.0)
            lv["dome"] = Tex(cloud_domes(al, px), half, px, 65535.0/1000)
        dem = {"L2": "L2_cop.npy", "LM": "LM_cop.npy"}.get(name)
        if relief and dem and os.path.exists(D(dem)):
            h = np.load(D(dem)).astype(np.float32)
            land = np.array(a[3]) > 0.5
            h = np.where(cv2.GaussianBlur(land.astype(np.float32), (0, 0), 1.5) > 0.5, np.clip(h, 0, None), 0)
            lv["dem"] = Tex(cv2.GaussianBlur(h, (0, 0), 0.8), half, px, 100.0)
        if name == "L2" and os.path.exists(D("L2_light.npy")):
            lv["light"] = Tex(np.load(D("L2_light.npy")), half, px, 65535.0)
        L[name] = lv
        print("level", name, "loaded", {k: v.mips[0].shape for k, v in lv.items() if isinstance(v, Tex)}, flush=True)
    return L

ORDER = ["L2", "LM", "L1", "L0", "LG"]
def level_weights(L, x, y, fp):
    """per-pixel weight of each level: finest that resolves the footprint, soft blends in between"""
    rem = np.ones(x.shape, np.float32); W = {}
    last = [n for n in ORDER if n in L][-1]
    for name in ORDER:
        if name not in L: continue
        lv = L[name]
        if name == last:
            W[name] = rem; break
        ew = lv["rgb"].edge(x, y)
        if name == "L2": ew = np.minimum(ew, np.clip((30000-np.hypot(x, y))/14000, 0, 1))
        if name == "LM": ew = np.minimum(ew, np.clip((88000-np.hypot(x, y))/16000, 0, 1))
        rw = np.clip((np.log2(2.6*lv["px"])-np.log2(np.maximum(fp, 1e-3)))/1.5, 0, 1)
        w = ew*rw
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

def atmosphere(col, d, h_cam, h_hit, mu, dist_inf, warm):
    """apply transmittance + in-scattering. col: surface radiance (reflectance units)."""
    odr = optical_depth(h_cam, h_hit, mu, HR); odm = optical_depth(h_cam, h_hit, mu, HM)
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
    wd_all = np.clip((fpm-18.0)/30.0, 0, 1)*cand*okm*(tm > 0)
    if (wd_all > 0).any():
        jf = np.nonzero(wd_all > 0)
        Pm = C+d[jf]*tm[jf][:, None]
        xm_, ym_, _ = to_xy(Pm)
        xm_ += -WIND[0]*t; ym_ += -WIND[1]*t
        Wf = Wfun(xm_, ym_, fpm[jf])
        af, _ = sample_field(L, "alpha", xm_, ym_, fpm[jf]*1.5, Wf)
        cf = np.clip(af*0.9, 0, 1)
        cov[jf] = cf*wd_all[jf]; cdist[jf] = tm[jf]
        ccol[jf] = np.array([0.74, 0.75, 0.77], np.float32)*(0.92+0.08*cf[:, None])
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
    sunlit = np.clip((ndl+0.30)/1.30, 0, 1)**1.2
    base_dark = 0.55+0.45*np.sqrt(hrel)
    val = (0.70*sunlit+0.10)*base_dark
    rgb = np.stack([val*1.00+0.07, val*1.00+0.085, val*0.99+0.11], -1).astype(np.float32)*0.95
    edge = np.clip(al/0.55, 0, 1)
    cv = (edge*edge*(3-2*edge)).astype(np.float32)
    ii = (idx[0][sel[hi]], idx[1][sel[hi]])
    wn = 1-wd_all[ii]                                  # near-cloud share of this pixel
    ccol[ii] = ccol[ii]*(1-wn[:, None])+rgb*wn[:, None]
    cov[ii] = cov[ii]*(1-wn)+cv*wn; cdist[ii] = (a0[hi]+(a1[hi]-a0[hi])*s)
    return ccol, cov, cdist

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
    return R5.sky(d, C, None)

# ------------------------------------------------------------------ one frame
def render_frame(t, L, W, H, ss=1.25, cam=None, want_matte=False, stats=None):
    Ws, Hs = int(round(W*ss)), int(round(H*ss))
    cam = cam or cam_at(t, Ws, Hs)
    t_0 = time.time()
    d = cam.rays().astype(np.float64); C = cam.pos
    b = d@C; cc = C@C-R_E**2; disc = b*b-cc
    hit = disc > 0
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
    if cam.alt < 400000 and any("dem" in L[n] for n in Wl):
        for _ in range(3):
            hgt, ws = sample_field(L, "dem", x, y, fp, Wl)
            hh = hgt
            t2 = tt-hh/cosi
            P2 = C+d*t2[..., None]
            x, y, _ = to_xy(P2)
        tt = tt-hh/cosi
    col = np.zeros(x.shape+(3,), np.float32); wsum = np.zeros(x.shape, np.float32)
    for name, w in Wl.items():
        m = (w > 1e-4) & hit
        if m.any():
            col += L[name]["rgb"].sample(x, y, fp, mask=m, bias=-0.25)*w[..., None]; wsum += w
    col /= np.maximum(wsum, 1e-6)[..., None]
    t_tex = time.time()
    # Seliu in the light (matte), the rest a touch darker
    light = None
    if "L2" in L and "light" in L["L2"]:
        inside = (np.abs(x) < 31000) & (np.abs(y) < 31000)
        light = L["L2"]["light"].sample(x, y, fp, mask=inside)
        gl = TL.glow(t)
        if gl > 0:
            # +25 % on the island and its reef, -30 % around it, fading out with distance (no hard frame)
            near = np.clip((30000-np.hypot(x, y))/30000, 0, 1)**0.5
            k = 1+gl*(0.25*light-0.30*(1-light)*near)
            col *= k[..., None]
    # cloud shadows on the ground
    if fp.min() < 3000:
        sh = cloud_shadow(L, x, y, fp, t, Wl)
        col *= (1-0.50*sh)[..., None]
    # atmosphere on the ground
    h_cam = cam.alt
    mu = cosi
    warm = TL.warmth(t)
    col = atmosphere(col, d.astype(np.float32), h_cam, hh, mu, None, warm)
    # clouds
    t_cl = time.time()
    if fp.min() < 3000 and cam.alt < 400000:
        Wfun = lambda xx, yy, ff: level_weights(L, xx, yy, ff)
        ccol, cov, cdist = clouds(L, C, d, cam, (pix_ang/np.sqrt(cosi)).astype(np.float32), t, tt, hit, Wfun)
        if cov.max() > 0:
            # cloud tops seen through the air above them
            hc = np.full(cov.shape, CLOUD_BASE+200.0, np.float32)
            mu_c = np.clip(-(d.astype(np.float32)*nrm.astype(np.float32)).sum(-1), 0.02, 1)
            ccol = atmosphere(ccol, d.astype(np.float32), h_cam, hc, mu_c, None, warm)
            col = col*(1-cov[..., None])+ccol*cov[..., None]
    t_cle = time.time()
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

def blur_offsets(t, W, H):
    """shutter 180 deg (1/50 s): enough sub-frames that each moves < ~1.5 px"""
    med, mx = screen_speed(t, W, H)
    n = int(np.clip(math.ceil(med*0.5/1.5), 1, 8))
    if n == 1: return [0.0]
    return list(np.linspace(-0.25, 0.25, n)/TL.FPS)

# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode"); ap.add_argument("out"); ap.add_argument("times", nargs="*", type=float)
    ap.add_argument("--w", type=int, default=1920); ap.add_argument("--h", type=int, default=1080)
    ap.add_argument("--ss", type=float, default=1.25)
    ap.add_argument("--from_", type=float, default=0); ap.add_argument("--to", type=float, default=TL.DURATION)
    ap.add_argument("--every", type=int, default=1); ap.add_argument("--shard", default="0/1")
    ap.add_argument("--noblur", action="store_true"); ap.add_argument("--final", action="store_true")
    ap.add_argument("--clean", action="store_true", help="with --final: no graphics")
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    L = load_levels()
    if a.mode == "stills": jobs = [(None, t) for t in a.times]
    else:
        n0, n1 = int(round(a.from_*TL.FPS)), int(round(a.to*TL.FPS))
        jobs = [(f, f/TL.FPS) for f in range(n0, n1, a.every)]
    k, K = map(int, a.shard.split("/")); jobs = jobs[k::K]
    for f, t in jobs:
        name = f"t{t:06.2f}" if f is None else f"f{f:05d}"
        png = os.path.join(a.out, name+".png")
        if f is not None and os.path.exists(png): continue           # resume
        t0 = time.time()
        offs = [0.0] if a.noblur else blur_offsets(t, a.w, a.h)
        acc = None; st = {}
        for dt in offs:
            im, matte = render_frame(t+dt, L, a.w, a.h, a.ss, want_matte=True, stats=st)
            acc = im if acc is None else acc+im
        img = acc/len(offs)
        cp = TL.camera(t)
        rec = {"t": t, "frame": f, "camera": dict(zip(["lat", "lon", "range_m", "heading", "tilt", "roll"], cp)), "vfov": TL.VFOV,
               "alt_m": st.get("alt"), "subframes": len(offs), "sec": round(time.time()-t0, 1), "timing": {k: round(v, 2) for k, v in st.items() if k != "alt"}}
        if a.final:
            import grade_v8 as G, motion_gfx_v8 as M
            x = G.grade(img, t, matte)
            if not a.clean:
                x = M.draw(x, t, cam_at(t, a.w, a.h), fmt=TL.FMT)
            x = x*TL.fade(t)
            out = G.finish(x, seed=(f or int(t*1000)))
            cv2.imwrite(png, cv2.cvtColor(out, cv2.COLOR_RGB2BGR))
        else:
            cv2.imwrite(png, cv2.cvtColor((np.clip(img, 0, 1)*65535+0.5).astype(np.uint16), cv2.COLOR_RGB2BGR))
            if matte is not None:
                cv2.imwrite(os.path.join(a.out, name+"_matte.png"), (np.clip(matte, 0, 1)*255+0.5).astype(np.uint8))
        json.dump(rec, open(os.path.join(a.out, name+".json"), "w"))
        print(name, f"alt={rec['alt_m']/1000:.1f}km sub={len(offs)} {rec['sec']}s", rec["timing"], flush=True)

if __name__ == "__main__":
    main()
