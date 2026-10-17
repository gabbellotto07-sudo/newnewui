"""Seliu v9 — brand intro before the flight (client idea, 16:9, 5.6 s; the flight's t=0 is the intro's 5.6 s).
One real camera, no cut. It sits where the flight starts but looks away from the Earth, into the real stars.
  0.0-0.8   the Compass Rose (official logo, ivory) resolves out of the star field
  0.75-1.6  COMPASS ROSE (ivory) rises under a fine gold rule; INDONESIA (gold) fades in; the lockup holds to 2.6
  2.6-3.1   the words leave; the ring closes into a halo; the rose turns 22.5 deg and becomes an eight-ray star
            (it backs off 4 % and brightens: the anticipation)
  3.1-3.9   the star launches toward the camera in true 3D (perspective does the rush) and passes right of the
            lens, on the side of the Earth: it defocuses close up, a little veiling glare, the stars dip, a flinch
  3.95-5.6  the operator chases it: a 120 deg whip pan right (peak at ~29 %, a 5 deg bank, 180 deg shutter),
            the Earth swings in, the star is re-acquired ahead and bends into a shooting star in the dark above
            the limb; the pan is an offset that dies on the flight's own motion, so it lands on frame 0 with the
            flight's speed. The star dies by flight t=0.8 (drawn over the flight's first frames).
usage: intro_v9.py OUT_DIR FLIGHT_NOFADE_DIR    (1920x1080; writes i00000.png ... i00139.png, then f00000.png ...
       copies of the flight's first frames with the dying shooting star over them)"""
import sys, os, math, numpy as np, cv2
from scipy.spatial.transform import Rotation as Rot, Slerp
from scipy.interpolate import PchipInterpolator
from scipy.special import betainc
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_v9 as R, render as R5
import motion_gfx_v9 as M
from motion_gfx import SS, lin, smooth, out_cubic, out_quart, in_out_cubic
import grade_v9 as G

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, FPS = 1920, 1080, 25
T0 = 5.6                                   # intro time of the flight's t=0
PAN1 = 5.6                                 # (PAN0 follows the star's exit, below)
YAW0, PITCH0 = -72.0, 6.0                  # the hold looks this far left of (and above) where the flight looks
LAUNCH, SPEED, Z0 = 3.1, 55.0, 30.0        # star launch time, cruise speed (u/s), start depth (u)
PAN0 = 3.76                                # two frames after the star leaves the frame (T_EXIT, checked below)
VFOV = R.TL.VFOV
IVORY = np.array([0xF5, 0xEF, 0xE6], np.float32)/255
GOLDB = np.array([0xC9, 0xA6, 0x6B], np.float32)/255
WARM = np.array([1.0, 0.93, 0.80], np.float32)
FPX = H/2/math.tan(math.radians(VFOV/2))   # focal length in px
CX, CY = W/2, 452.0                        # the rose's centre on screen

# ------------------------------------------------------------------ the camera
class Cam(R5.Camera):
    def __init__(self, pos, Mx, W_, H_, vfov=VFOV):
        self.W, self.H = W_, H_; self.pos = np.asarray(pos, float)
        self.r, self.u, self.f = Mx[:, 0].copy(), Mx[:, 1].copy(), Mx[:, 2].copy()
        self.tanv = math.tan(math.radians(vfov)/2); self.tanh = self.tanv*W_/H_
        self.alt = np.linalg.norm(self.pos)-R.R_E

def basis(c): return np.stack([c.r, c.u, c.f], 1)

_c0, _c1 = R.cam_at(0.0, W, H), R.cam_at(0.04, W, H)
P0, V0 = _c0.pos, (_c1.pos-_c0.pos)/0.04
M0 = basis(_c0); OMEGA = Rot.from_matrix(basis(_c1)@M0.T).as_rotvec()/0.04

def flight_pose(tb):
    """the flight's camera, extrapolated before t=0 (constant linear and angular velocity)"""
    if tb >= 0:
        c = R.cam_at(tb, W, H); return c.pos, basis(c)
    return P0+V0*tb, Rot.from_rotvec(OMEGA*tb).as_matrix()@M0

def local(yaw=0.0, pitch=0.0, roll=0.0):
    """rotation in camera coordinates: yaw + = turn right, pitch + = look up, roll + = image turns clockwise"""
    return (Rot.from_rotvec([0, math.radians(yaw), 0])*Rot.from_rotvec([-math.radians(pitch), 0, 0])
            *Rot.from_rotvec([0, 0, -math.radians(roll)]))

OFF0 = local(YAW0, PITCH0)
_slerp = Slerp([0, 1], Rot.concatenate([OFF0, Rot.identity()]))

def pan_u(tau): return min(max((tau-PAN0)/(PAN1-PAN0), 0.0), 1.0)

def flinch(tau):          # the camera flinches as the star passes (0.4 deg roll, damped)
    x = tau-3.86
    return 0.0 if x < 0 else 0.4*math.sin(2*math.pi*x/0.30)*math.exp(-x/0.18)

def bank(u):              # 5 deg into the turn, peak at ~24 %, back to level by 85 %
    x = min(u/0.85, 1.0); return 5.0*(x*(1-x)**2.5)/((1/3.5)*(2.5/3.5)**2.5) if 0 < x < 1 else 0.0

def pose(tau):
    """-> camera position, basis. Before the pan: the hold (still). In the pan: offset dying on the flight."""
    u = pan_u(tau)
    tb = -(PAN1-PAN0)+(PAN1-PAN0)*(2*u*u-u**3)        # the flight's clock eases in, matched at u = 1
    if tau >= PAN1: tb = tau-T0
    pos, Mf = flight_pose(tb)
    s = float(betainc(1.6, 4.0, u))
    off = _slerp([s])[0]*local(roll=bank(u)+flinch(tau))
    return pos, Mf@off.as_matrix()

def cam(tau, W_=W, H_=H, vfov=VFOV):
    p, Mx = pose(tau); return Cam(p, Mx, W_, H_, vfov)

# ------------------------------------------------------------------ the star's path (moves with the camera, not with its turn)
_ph = pose(PAN0-0.01)[1]                                  # the hold basis
def _local_dir(sx, sy, Mx):
    x = (sx/W*2-1)*math.tan(math.radians(VFOV/2))*W/H; y = (1-sy/H*2)*math.tan(math.radians(VFOV/2))
    v = Mx@np.array([x, y, 1.0]); return v/np.linalg.norm(v)

def _phys(tau):
    """straight flight toward the lens: start Z0 ahead behind the rose, pass at (5, -1.5, 0) in the hold frame"""
    d0 = _ph.T@_local_dir(CX, CY, _ph)*Z0/(_ph.T@_local_dir(CX, CY, _ph))[2]
    p1 = np.array([5.0, -1.5, 0.0]); L = np.linalg.norm(p1-d0); e = (p1-d0)/L
    t = max(tau-LAUNCH, 0.0); ta = 0.18
    s = SPEED*t**4/(4*ta**3) if t < ta else SPEED*ta/4+SPEED*(t-ta)
    return d0+e*s                                          # hold-local coordinates

def size_near(d): return 70.0*(Z0/max(d, 0.5))**1.4          # ray length (px): a touch faster than 1/d, for the rush

def _exit_time():
    for tau in np.arange(LAUNCH, LAUNCH+2.0, 0.01):
        q = _phys(tau)
        if q[2] <= 0.3: return tau
        x = W/2*(1+q[0]/q[2]/math.tan(math.radians(VFOV/2))/(W/H)); y = H/2*(1-q[1]/q[2]/math.tan(math.radians(VFOV/2)))
        r = 0.25*size_near(np.linalg.norm(q))
        if x-r > W or y-r > H: return tau
    return LAUNCH+1.0
T_EXIT = round(float(_exit_time()), 2)
assert abs(PAN0-(T_EXIT+0.08)) < 0.011, (T_EXIT, PAN0)       # the operator reacts two frames late
def _yp(v):  return math.atan2(v[0], v[2]), math.asin(np.clip(v[1]/np.linalg.norm(v), -1, 1))
def _key_dir(tau, sx, sy):
    p, Mx = pose(tau) if tau < PAN1 else flight_pose(tau-T0)
    return _ph.T@_local_dir(sx, sy, Mx)

# after the pass the star bends round and becomes a shooting star crossing the sky above the flight's first view
# at a steady speed: a straight screen line in the flight's t=0 frame (so its trail keeps one length)
_Mref = flight_pose(0.0)[1]
def _to_ref(v):                                              # world direction -> screen of the flight's t=0 frame
    z = v@_Mref[:, 2]; return np.array([W/2*(1+(v@_Mref[:, 0])/z/(math.tan(math.radians(VFOV/2))*W/H)), H/2*(1-(v@_Mref[:, 1])/z/math.tan(math.radians(VFOV/2)))])
TA, TB = 4.95, 6.4                                           # re-acquired at the top right of the turning frame at TA
SA, SB = _to_ref(_local_dir(0.97*W, 0.12*H, pose(TA)[1])), np.array([0.40*W, 0.24*H])
def _sky(tau):
    q = SA+(SB-SA)*(tau-TA)/(TB-TA); return _ph.T@_local_dir(q[0], q[1], _Mref)
_keys = [(t, _phys(t)/np.linalg.norm(_phys(t))) for t in (T_EXIT-0.08, T_EXIT-0.04, T_EXIT)]
_keys += [(t, _sky(t)) for t in (TA, TA+0.1, TA+0.2)]
_kt = np.array([k[0] for k in _keys]); _kyp = np.array([_yp(k[1]) for k in _keys])
_kyp[:, 0] = np.unwrap(_kyp[:, 0])
_fy, _fp = PchipInterpolator(_kt, _kyp[:, 0]), PchipInterpolator(_kt, _kyp[:, 1])

def star3d(tau):
    """-> world direction from the camera, distance (u)"""
    if tau <= T_EXIT:
        q = _phys(tau); d = np.linalg.norm(q); return _ph@(q/d), d
    if tau >= TA:
        v = _sky(tau)
    else:
        y, p = float(_fy(tau)), float(_fp(tau))
        v = np.array([math.sin(y)*math.cos(p), math.sin(p), math.cos(y)*math.cos(p)])
    d = np.linalg.norm(_phys(T_EXIT))+SPEED*0.9*(tau-T_EXIT)
    return _ph@v, d

def star_screen(tau, c):
    v, d = star3d(tau)
    z = v@c.f
    if z <= 1e-3: return None, d, z
    return np.array([c.W/2*(1+(v@c.r)/z/c.tanh), c.H/2*(1-(v@c.u)/z/c.tanv)]), d, z

# ------------------------------------------------------------------ sprites
_logo = None
def logo_alpha(px):
    global _logo
    if _logo is None:
        a = cv2.imread(os.path.join(ROOT, "brand", "compass-rose-logo-oro-800.png"), cv2.IMREAD_UNCHANGED)
        _logo = a[..., 3].astype(np.float32)/255
    return cv2.resize(_logo, (px, px), interpolation=cv2.INTER_AREA if px < 800 else cv2.INTER_CUBIC)

def ring_mask(px):
    yy, xx = np.mgrid[0:px, 0:px].astype(np.float32)
    r = np.hypot(xx-(px-1)/2, yy-(px-1)/2)/(px/2)
    return np.clip((r-0.86)/0.04, 0, 1)

def star_sprite(size, rot, core=1.0, rays=1.0, cr=0.10, hr=0.35):
    """the eight-ray star (the rose's own eight points): long N/E/S/W rays, shorter diagonals, soft core"""
    n = int(size*2.2)|1; c = n//2
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)-c
    r = np.hypot(xx, yy)+1e-3; th = np.arctan2(yy, xx)-math.radians(rot)
    img = core*np.exp(-(r/(cr*size+0.6))**2)+0.35*core*np.exp(-(r/(hr*size+1.0))**2)
    if rays > 0:
        for k in range(8):
            a = k*math.pi/4; L = size*(1.0 if k % 2 == 0 else 0.55)
            d = np.abs(np.sin(th-a))*r; along = np.cos(th-a)*r; wr = max(1.0, 0.007*size)
            img += rays*0.95*np.exp(-(d/wr)**2)*np.clip(1-along/L, 0, 1)**2*(along > 0)
    return np.clip(img, 0, 1.5)

def add_sprite(img, spr, x, y, color, gain=1.0, blur_vec=(0, 0), defocus=0.0):
    Hh, Ww = img.shape[:2]
    if defocus > 0.6:
        r = int(round(defocus)); k = np.zeros((2*r+1, 2*r+1), np.float32); cv2.circle(k, (r, r), r, 1.0, -1, cv2.LINE_AA)
        spr = cv2.filter2D(np.pad(spr, r), -1, k/k.sum())
    if abs(blur_vec[0])+abs(blur_vec[1]) > 1.0:
        L = int(min(math.hypot(*blur_vec), 600)); k = np.zeros((2*L+1, 2*L+1), np.float32)
        cv2.line(k, (L-int(blur_vec[0]/2), L-int(blur_vec[1]/2)), (L+int(blur_vec[0]/2), L+int(blur_vec[1]/2)), 1.0, 1, cv2.LINE_AA)
        spr = cv2.filter2D(np.pad(spr, L), -1, k/k.sum())
    n = spr.shape[0]; c = n//2
    x0, y0 = int(round(x))-c, int(round(y))-c
    X0, Y0, X1, Y1 = max(x0, 0), max(y0, 0), min(x0+n, Ww), min(y0+n, Hh)
    if X1 <= X0 or Y1 <= Y0: return img
    s = spr[Y0-y0:Y1-y0, X0-x0:X1-x0]*gain
    img[Y0:Y1, X0:X1] = 1-(1-img[Y0:Y1, X0:X1])*(1-np.clip(s[..., None]*color, 0, 1))
    return img

# ------------------------------------------------------------------ the real stars, streaked by the turn (plate level)
def stars_plate(img, tau, gain):
    v, col, br = R._stars()
    dt = 0.5/FPS
    ca, cb = cam(tau-dt/2), cam(tau+dt/2)
    pa, za = ca.project(ca.pos+v*1e13); pb, zb = cb.project(cb.pos+v*1e13)
    C = ca.pos; b = v@C; disc = b*b-(C@C-R.R_E**2)
    ok = (za > 0) & (zb > 0) & ~((disc > 0) & (b < 0))
    s = 0.75; r = 3
    for a_, b_, c_, w_ in zip(pa[ok], pb[ok], col[ok], br[ok]):
        L = float(np.hypot(*(b_-a_))); n = max(1, int(math.ceil(L/1.0)))
        if max(a_[0], b_[0]) < -4 or min(a_[0], b_[0]) > W+4 or max(a_[1], b_[1]) < -4 or min(a_[1], b_[1]) > H+4: continue
        for k in range(n):
            x, y = a_+(b_-a_)*((k+0.5)/n)
            ix, iy = int(round(x)), int(round(y))
            x0, x1, y0, y1 = max(ix-r, 0), min(ix+r+1, W), max(iy-r, 0), min(iy+r+1, H)
            if x1 <= x0 or y1 <= y0: continue
            yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
            gk = np.exp(-((xx-x)**2+(yy-y)**2)/(2*s*s)); gk /= max(gk.max(), 1e-6)
            patch = img[y0:y1, x0:x1]
            dark = np.clip((0.10-patch.mean(-1))/0.08, 0, 1)
            img[y0:y1, x0:x1] = patch+(gk*dark*w_*gain/n)[..., None]*c_
    return img

# ------------------------------------------------------------------ the Earth in the pan: one wide render per frame,
# the turn inside the shutter re-projected from it (the camera barely translates in 1/50 s)
L_ = None
def earth_plate(tau):
    global L_
    if L_ is None:
        L_ = R.load_levels(names=("LG", "L0"))         # from 5,500+ km only these two levels carry weight
    dt = 0.5/FPS
    ca, cc, cb = cam(tau-dt/2), cam(tau), cam(tau+dt/2)
    sweep = max(math.degrees(math.acos(np.clip(ca.f@cb.f, -1, 1))), math.degrees(math.acos(np.clip(ca.u@cb.u, -1, 1))))
    m = sweep/2+1.5
    hv, hh = math.radians(VFOV/2+m), math.atan(math.tan(math.radians(VFOV/2))*W/H)+math.radians(m)
    Hw = int(math.ceil(H*math.tan(hv)/math.tan(math.radians(VFOV/2)))); Ww = int(math.ceil(Hw*math.tan(hh)/math.tan(hv)))
    ss = 1.25
    wide = Cam(cc.pos, basis(cc), int(round(Ww*ss)), int(round(Hw*ss)), math.degrees(2*hv))
    wide.tanh = math.tan(hh)
    img, matte = R.render_frame(0.0, L_, Ww, Hw, ss, cam=wide, want_matte=True)
    wide_px = Cam(cc.pos, basis(cc), Ww, Hw, math.degrees(2*hv)); wide_px.tanh = math.tan(hh)
    px_per_deg = H/VFOV
    N = int(np.clip(math.ceil(sweep*px_per_deg/1.2), 1, 64))
    acc = np.zeros((H, W, 3), np.float32); mt = None
    for k in range(N):
        tk = tau+dt*((k+0.5)/N-0.5)
        c = cam(tk); c.pos = cc.pos
        d = c.rays()
        p, z = wide_px.project(c.pos+d)
        mx, my = p[..., 0].astype(np.float32)-0.5, p[..., 1].astype(np.float32)-0.5
        acc += cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        if k == N//2 and matte is not None:
            mt = cv2.remap(matte, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return acc/N, mt, N

def space_plate():
    """the black of space as the flight renders it (no Earth in the hold view)"""
    R.add_stars = lambda img, t, W_, H_: img
    global L_
    if L_ is None: L_ = R.load_levels(names=("LG", "L0"))
    img, _ = R.render_frame(0.0, L_, W, H, 1.0, cam=cam(1.0, W, H), want_matte=False)
    return img

# ------------------------------------------------------------------ the logo, the words, the star
def logo_layer(img, tau):
    p_in = lin(tau, 0.15, 0.8)
    k_c = ease3(lin(tau, 2.75, 3.05))
    antic = 0.04*smooth(lin(tau, 2.95, 3.1))
    scale = (0.97+0.03*out_cubic(p_in)+0.010*max(tau-0.8, 0))*(1-0.93*k_c)
    rot = 22.5*in_out_cubic(lin(tau, 2.6, 3.1))
    if tau < 3.12 and p_in > 0:
        D = 300
        src = logo_alpha(800); src = src*(1-ring_mask(800)*smooth(lin(tau, 2.6, 2.95)))
        sc = D*scale/800
        if sc < 0.5: src = cv2.resize(src, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA); sc *= 2
        n = src.shape[0]
        Mr = cv2.getRotationMatrix2D(((n-1)/2, (n-1)/2), -rot, sc)
        Mr[:, 2] += [CX-(n-1)/2, CY-(n-1)/2]
        full = cv2.warpAffine(src, Mr, (W, H), flags=cv2.INTER_AREA if sc < 1 else cv2.INTER_LINEAR)   # sub-pixel: no 1 px steps
        vis = smooth(lin(p_in, 0.25, 1.0))*(1-smooth(lin(k_c, 0.45, 0.85)))
        glow = cv2.GaussianBlur(full, (0, 0), 6+10*(1-p_in))*(0.9*math.sin(math.pi*min(p_in, 1))+0.8*k_c)
        img = img*(1-(full*vis)[..., None])+IVORY*(full*vis)[..., None]
        img = 1-(1-img)*(1-np.clip(glow[..., None]*WARM*0.55, 0, 1))
    if 2.9 <= tau < LAUNCH:
        b = smooth(lin(tau, 2.9, 3.05))
        img = add_sprite(img, star_sprite(70*(1-antic), rot), CX, CY, IVORY, gain=b*(1+0.3*smooth(lin(tau, 2.95, 3.1))))
    # words: COMPASS ROSE (ivory) rises under a gold rule, INDONESIA (gold) fades; they leave staggered
    cv = M.Canvas(W, H, "16x9"); k = cv.k
    a1, pad1, asc1, desc1, w1 = M.text_block("COMPASS ROSE", "title", k, 0.62)
    a2, pad2, asc2, desc2, w2 = M.text_block("INDONESIA", "place", k, 0.62)
    o1, orl, o2 = (1-smooth(lin(tau, 2.6+d, 2.95+d)) for d in (0.0, 0.08, 0.16))
    y1 = 715.0
    p1 = lin(tau, 0.75, 1.45)
    if p1 > 0 and max(o1, o2) > 0:
        M.put(cv, M.g_mask(a1, p1, pad1, asc1, desc1), CX-w1/SS/2, y1, pad1, asc1, o1, color=IVORY)
        r = out_quart(lin(tau, 0.65, 1.35)); Lr = 120*k*r
        if Lr > 1 and orl > 0:
            xs = np.linspace(CX-Lr, CX+Lr, 31); al = np.clip(1.2-np.abs(np.linspace(-1, 1, 31))**2, 0, 1)*0.85*orl
            cv.stroke(np.stack([xs, np.full(31, y1-asc1/SS-30*k)], 1), 1.6*k, al, GOLDB, chunks=12)
        p2 = lin(tau, 1.1, 1.65)
        if p2 > 0:
            M.put(cv, M.g_fade(a2, p2), CX-w2/SS/2, y1+64*k, pad2, asc2, o2, color=GOLDB)
    return cv.composite(np.clip(img, 0, 1))

def ease3(x): x = min(max(x, 0.0), 1.0); return x*x*x

def life(tau):
    """the star's brightness: full, then a last flare (+40 % over 3 frames) and an exponential death"""
    td = T0+0.32
    if tau < td: return 1.0
    x = tau-td
    if x < 0.12: return 1.0+0.4*math.sin(math.pi*x/0.12)
    return math.exp(-(x-0.12)/0.25)*(tau < T0+0.85)

def flying_star(img, tau, c=None):
    """the star after the launch: 3D, motion-blurred within the shutter; a shooting star with a tail once it is far"""
    if tau < LAUNCH or tau > T0+0.85: return img
    c = c or (cam(tau) if tau < PAN1 else R.cam_at(tau-T0, W, H))
    camf = (lambda t: cam(t) if t < PAN1 else R.cam_at(t-T0, W, H))
    dt = 0.5/FPS
    p, d, z = star_screen(tau, c)
    if p is None: return img
    pa, _, _ = star_screen(tau-dt/2, camf(tau-dt/2)); pb, _, _ = star_screen(tau+dt/2, camf(tau+dt/2))
    bv = (0, 0) if pa is None or pb is None else (pb[0]-pa[0], pb[1]-pa[1])
    near = tau <= T_EXIT+0.05
    lv = life(tau)
    if near:
        size = size_near(d)
        defoc = 0.0
        rays = 1.0
    else:
        far = smooth(lin(tau, PAN0+0.45*(PAN1-PAN0), T0))
        size = max(size_near(d), 8.5)*(1-0.35*far); defoc = 0.0; rays = 0.55*(1-far)
    if size > 1600 or not (-size*1.2 < p[0] < W+size*1.2 and -size*1.2 < p[1] < H+size*1.2): return img
    # the tail: where it was in the last ~0.3 s, seen by the camera now (a meteor's trail), ivory to gold
    if not near:
        tail_on = smooth(lin(tau, PAN0+0.5*(PAN1-PAN0), PAN1))
        hist = np.linspace(tau-0.28, tau, 42); pts = []
        for th in hist:
            q, _, zz = star_screen(th, c)
            if q is not None: pts.append(q)
        if tail_on > 0 and len(pts) > 3:
            pts = np.array(pts); cvs = M.Canvas(W, H, "16x9")
            al = (np.linspace(0, 1, len(pts))**2.2)*0.8*tail_on*min(lv, 1.0)
            n = len(pts)
            for i in range(0, n-1, 3):                                  # gold fading to ivory toward the head
                j = min(i+4, n); w_ = (i+j)/2/n
                cvs.stroke(pts[i:j], 2.0+0.6*w_, al[i:j], GOLDB*(1-w_**2)+IVORY*w_**2, chunks=1)
            cvs.glow_poly(pts[-10:], 5, M.GOLD, 0.25*tail_on*min(lv, 1.0))
            img = cvs.composite(img)
    kn = smooth(lin(size, 80, 300)) if near else 0.0               # close up: a hot small core, sharp rays, short streak
    img = add_sprite(img, star_sprite(min(size, 1500), 22.5+40*smooth(lin(tau, LAUNCH, T_EXIT)), rays=rays,
                                      cr=0.10-0.06*kn, hr=0.35-0.2*kn), p[0], p[1], IVORY,
                     gain=lv, blur_vec=(bv[0]*(1-0.7*kn), bv[1]*(1-0.7*kn)), defocus=defoc)
    # bloom around the head (never a white-out: <= 25 % of the frame)
    kb = smooth(lin(size, 120, 420))
    if near and kb > 0:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        rr = np.hypot(xx-p[0], yy-p[1])/min(0.12*size+12, 0.25*H)
        bloom = (np.exp(-rr*rr)*0.40+np.exp(-rr)*0.10)*kb
        img = 1-(1-img)*(1-np.clip(bloom[..., None]*WARM*lv, 0, 1))
    return img

def pass_k(tau):   # how close the star is (0..1), for the glare and the exposure dip
    return smooth(lin(tau, 3.55, 3.84))*(1-smooth(lin(tau, 3.86, 4.25)))

# ------------------------------------------------------------------ one frame
def intro_frame(tau, black):
    if tau < PAN0-0.06:
        img = black.copy(); mt = None
    else:
        img, mt, N = earth_plate(tau)
    u = pan_u(tau)
    ex = 1.0+0.20*smooth(lin(u, 0.55, 0.8))*(1-smooth(lin(u, 0.8, 1.0)))        # Earth arrives a touch hot, settles
    img = img*ex
    sg = smooth(lin(tau, 0.0, 0.25))*(1-0.25*pass_k(tau))*(1+1.0*(1-smooth(lin(tau, 4.4, 5.4))))   # the eye is dark-adapted before the Earth
    img = stars_plate(img, tau, sg)
    x = G.grade(img, 0.0, mt)
    x = x*smooth(lin(tau, 0.0, 0.24))                                           # 6 frames from black
    x = logo_layer(x, tau)
    x = flying_star(x, tau)
    g = 0.015*pass_k(tau)                                                        # veiling glare at the pass
    if g > 0: x = 1-(1-x)*(1-g*WARM)
    return x

def main():
    out_dir, flight_dir = sys.argv[1:3]
    only = sys.argv[3] if len(sys.argv) > 3 else None                            # "a:b" frame range (tests)
    os.makedirs(out_dir, exist_ok=True)
    black = space_plate()
    n = int(round(T0*FPS))
    rng = range(n) if only is None else range(*map(int, only.split(":")))
    workers = int(os.environ.get("INTRO_WORKERS", "1")); rng = list(rng)
    if workers > 1:
        import gc; gc.collect(); gc.freeze()
        kids = []
        for wk in range(1, workers):
            pid = os.fork()
            if pid == 0: rng = rng[wk::workers]; kids = None; break
            kids.append(pid)
        if kids is not None: rng = rng[0::workers]
    for f in rng:
        if f >= n: continue
        png = os.path.join(out_dir, f"i{f:05d}.png")
        if os.path.exists(png): continue
        x = intro_frame(f/FPS, black)
        cv2.imwrite(png, cv2.cvtColor(G.finish(x, seed=90000+f), cv2.COLOR_RGB2BGR))
        print("intro", f, flush=True)
    if only is None and (workers == 1 or rng == list(range(n))[0::workers]):
        for f in range(0, int(0.86*FPS)+1):
            src = os.path.join(flight_dir, f"f{f:05d}.png")
            if not os.path.exists(src): continue
            x = cv2.cvtColor(cv2.imread(src), cv2.COLOR_BGR2RGB).astype(np.float32)/255
            x = flying_star(x, T0+f/FPS)
            cv2.imwrite(os.path.join(out_dir, f"f{f:05d}.png"), cv2.cvtColor((np.clip(x, 0, 1)*255+0.5).astype(np.uint8), cv2.COLOR_RGB2BGR))
    if workers > 1:
        if kids is None: os._exit(0)
        for pid in kids: os.waitpid(pid, 0)

if __name__ == "__main__":
    main()
