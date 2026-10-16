"""Seliu v6 -- motion graphics layer (texts, dots, flight arcs, boat route, Seliu outline).

    draw(img, t, cam, fmt="16x9") -> img       img float32 HxWx3 in 0..1 (graded plate), t seconds

Everything is anchored to real places through cam.project(render.ecef(lat, lon, h)), so the graphics
sit on the existing plates without any 3D re-render. Internally:
  * an INK layer (premultiplied RGBA) at SS x supersampling for crisp, anti-aliased type and lines;
  * a GLOW layer (additive, half resolution, blurred twice) for comet heads, line glow, outline flash;
  * a soft SHADOW (and a faint wide scrim under titles) derived from the ink alpha, for legibility
    on bright reef flats and turquoise water, on a phone.
Text is set glyph by glyph (kerning-aware advances) so every letter can carry its own opacity,
blur, rise and tracking. Moving elements get a directional motion blur from their screen velocity.

Direction and timing: docs/05-direzione-grafica.md. Data: only the approved texts and coordinates.
"""
import os, sys, json, math
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geo import PLACES, xy, lonlat           # noqa: E402
from render import ecef, R_E                 # noqa: E402  (render imports are light: no data loaded)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(ROOT, "fonts")

# ------------------------------------------------------------------ palette (linear-ish display values)
INK = np.array([1.0, 0.969, 0.910], np.float32)        # #FFF7E8 warm white: all type
LINE = np.array([1.0, 0.955, 0.875], np.float32)       # lines, a hair warmer than type
GOLD = np.array([1.0, 0.86, 0.62], np.float32)         # glow / comet heads / outline light
SHORE = np.array([1.0, 0.90, 0.70], np.float32)        # Seliu outline: champagne light, distinct from white sand
UNDER = np.array([0.02, 0.06, 0.07], np.float32)       # dark under-stroke that separates the outline from the beach
SS = 2                                                 # supersampling of the ink layer

# ------------------------------------------------------------------ type system (px at 1080 short side)
TYPE = {
    "title":    dict(size=96, weight=360, italic=False, track=0.40),   # BELITUNG, SELIU ISLAND
    "subtitle": dict(size=34, weight=500, italic=False, track=0.18),   # spaced caps under titles
    "place":    dict(size=36, weight=500, italic=False, track=0.20),   # SINGAPORE, JAKARTA, TELUK GEMBIRA, BELITUNG (small)
    "note":     dict(size=42, weight=400, italic=True,  track=0.02),   # Direct flights, 15-20 min by boat
}
GEOM = dict(line=2.6, route=2.8, outline=2.4, dot=5.5, ring=1.3)       # px at 1080

# ------------------------------------------------------------------ easing
def clamp01(x): return min(max(x, 0.0), 1.0)
def lin(t, a, b): return clamp01((t-a)/(b-a)) if b > a else float(t >= a)
def smooth(x): x = clamp01(x); return x*x*(3-2*x)
def out_cubic(x): x = clamp01(x); return 1-(1-x)**3
def out_quart(x): x = clamp01(x); return 1-(1-x)**4
def out_expo(x): x = clamp01(x); return 1.0 if x >= 1 else 1-2**(-10*x)
def in_cubic(x): x = clamp01(x); return x**3
def in_out_cubic(x):
    x = clamp01(x); return 4*x**3 if x < 0.5 else 1-(-2*x+2)**3/2
def in_out_sine(x): x = clamp01(x); return 0.5-0.5*math.cos(math.pi*x)
def in_out_quint(x):
    x = clamp01(x); return 16*x**5 if x < 0.5 else 1-(-2*x+2)**5/2

# ------------------------------------------------------------------ timing chart (seconds, 25 fps)
# one place to retime everything; frame = round(t*25)
T = dict(
    sin_dot=2.30, sin_label=2.45, cgk_dot=2.80, cgk_label=2.95,
    arc_sin=(4.20, 7.00), arc_cgk=(4.70, 7.50),
    flights_note=5.30, tjq_arrive=7.00,
    bel_small=7.55, region_out=(8.20, 9.30),
    bel_title=10.40, bel_rule=10.90, bel_sub=11.15, bel_out=13.00,
    outline=(15.90, 18.30), outline_flash=18.30,
    seliu_title=17.20, seliu_sub=18.05,
    tg_dot=19.00, tg_label=19.15,
    route=(19.80, 22.40), boat_note=21.00, jetty=22.40,
    glint=(22.50, 24.70),
)

# ------------------------------------------------------------------ fonts & glyphs
_fonts, _glyphs = {}, {}
def font(px, weight, italic):
    k = (px, weight, italic)
    if k not in _fonts:
        f = ImageFont.truetype(os.path.join(FONTS, "Jost-Italic-VF.ttf" if italic else "Jost-VF.ttf"), px)
        f.set_variation_by_axes([weight]); _fonts[k] = f
    return _fonts[k]

def glyph(c, px, weight, italic):
    """alpha mask (float32) of one glyph at px size; offset of its top-left from the pen (baseline)"""
    k = (c, px, weight, italic)
    if k not in _glyphs:
        f = font(px, weight, italic)
        bb = f.getbbox(c, anchor="ls")
        if bb[2] <= bb[0] or bb[3] <= bb[1]:
            _glyphs[k] = (None, (0, 0))
        else:
            pad = 2
            im = Image.new("L", (bb[2]-bb[0]+2*pad, bb[3]-bb[1]+2*pad), 0)
            ImageDraw.Draw(im).text((pad-bb[0], pad-bb[1]), c, font=f, fill=255, anchor="ls")
            _glyphs[k] = (np.asarray(im, np.float32)/255.0, (bb[0]-pad, bb[1]-pad))
    return _glyphs[k]

def layout(s, px, weight, italic, track):
    """pen x of each glyph (kerning-aware) and total advance width, tracking in em"""
    f = font(px, weight, italic); xs = []; x = 0.0
    for i, c in enumerate(s):
        xs.append(x)
        nxt = s[i+1] if i+1 < len(s) else None
        adv = (f.getlength(c+nxt)-f.getlength(nxt)) if nxt else f.getlength(c)
        x += adv+(track*px if nxt else 0.0)
    return xs, x

# ------------------------------------------------------------------ canvas
class Canvas:
    def __init__(self, W, H, fmt):
        self.W, self.H, self.fmt = W, H, fmt
        self.k = min(W, H)/1080.0                        # px scale
        self.ink = np.zeros((H*SS, W*SS, 4), np.float32)  # premultiplied RGBA at SS x
        self.glow = np.zeros((H//2, W//2, 3), np.float32)  # additive, half res
        self.scrim = np.zeros((H//4, W//4), np.float32)   # wide soft darkening under titles (quarter res)
        # safe area (title/action safe, plus room for phone UI in 9:16)
        if fmt == "9x16": self.safe = (0.07*W, 0.12*H, 0.93*W, 0.86*H)
        else: self.safe = (0.05*W, 0.07*H, 0.95*W, 0.93*H)

    # -- low-level compositing -------------------------------------------------------
    def over(self, a, x0, y0, color, opacity=1.0):
        """composite alpha patch a (at SS res) with its top-left at integer SS px (x0, y0)"""
        if opacity <= 0.002 or a is None: return
        h, w = a.shape
        X0, Y0 = max(x0, 0), max(y0, 0); X1, Y1 = min(x0+w, self.ink.shape[1]), min(y0+h, self.ink.shape[0])
        if X1 <= X0 or Y1 <= Y0: return
        src = a[Y0-y0:Y1-y0, X0-x0:X1-x0]*opacity
        dst = self.ink[Y0:Y1, X0:X1]
        inv = (1-src)[..., None]
        dst[..., :3] = dst[..., :3]*inv+src[..., None]*color
        dst[..., 3] = dst[..., 3]*inv[..., 0]+src

    def glow_poly(self, pts, width, color, inten):
        """add a stroke to the glow layer (pts at 1x px)"""
        if inten <= 0.002 or len(pts) < 2: return
        m = np.zeros(self.glow.shape[:2], np.uint8)
        p = np.round(np.asarray(pts, np.float64)/2*16).astype(np.int32)
        cv2.polylines(m, [p], False, 255, max(1, int(round(width/2))), cv2.LINE_AA, shift=4)
        self.glow += (m.astype(np.float32)/255*inten)[..., None]*color

    def glow_dot(self, p, r, color, inten):
        if inten <= 0.002: return
        m = np.zeros(self.glow.shape[:2], np.uint8)
        c = (int(round(p[0]/2*16)), int(round(p[1]/2*16)))
        cv2.circle(m, c, max(1, int(round(r/2*16))), 255, -1, cv2.LINE_AA, shift=4)
        self.glow += (m.astype(np.float32)/255*inten)[..., None]*color

    # -- strokes ------------------------------------------------------------------------
    def stroke(self, pts, width, alphas, color=LINE, chunks=24):
        """polyline (1x px) with per-vertex alpha; drawn at SS x with sub-pixel AA"""
        pts = np.asarray(pts, np.float64)
        if len(pts) < 2: return
        alphas = np.broadcast_to(np.asarray(alphas, np.float64), (len(pts),))
        lw = max(1, int(round(width*SS)))
        P = pts*SS
        m = int(lw+4)
        x0, y0 = int(math.floor(P[:, 0].min()))-m, int(math.floor(P[:, 1].min()))-m
        x1, y1 = int(math.ceil(P[:, 0].max()))+m, int(math.ceil(P[:, 1].max()))+m
        X0, Y0 = max(x0, 0), max(y0, 0); X1, Y1 = min(x1, self.ink.shape[1]), min(y1, self.ink.shape[0])
        if X1 <= X0 or Y1 <= Y0: return
        mask = np.zeros((Y1-Y0, X1-X0), np.uint8)
        Q = np.round((P-[X0, Y0])*16).astype(np.int32)
        n = len(pts); idx = np.linspace(0, n-1, min(chunks, n-1)+1).round().astype(int)
        for a, b in zip(idx[:-1], idx[1:]):
            if b <= a: continue
            al = float(alphas[a:b+1].mean())
            if al <= 0.004: continue
            cv2.polylines(mask, [Q[a:b+1]], False, int(round(255*min(al, 1))), lw, cv2.LINE_AA, shift=4)
        self.over(mask.astype(np.float32)/255, X0, Y0, color)

    def disc(self, p, r, alpha, color=LINE):
        if alpha <= 0.004: return
        R = r*SS; x0, y0 = int(p[0]*SS-R-3), int(p[1]*SS-R-3)
        sz = int(2*R+7)
        m = np.zeros((sz, sz), np.uint8)
        c = (int(round((p[0]*SS-x0)*16)), int(round((p[1]*SS-y0)*16)))
        cv2.circle(m, c, max(1, int(round(R*16))), 255, -1, cv2.LINE_AA, shift=4)
        self.over(m.astype(np.float32)/255, x0, y0, color, alpha)

    def ring(self, p, r, width, alpha, color=LINE):
        if alpha <= 0.004: return
        R = r*SS; x0, y0 = int(p[0]*SS-R-6), int(p[1]*SS-R-6)
        sz = int(2*R+13)
        m = np.zeros((sz, sz), np.uint8)
        c = (int(round((p[0]*SS-x0)*16)), int(round((p[1]*SS-y0)*16)))
        cv2.circle(m, c, int(round(R*16)), 255, max(1, int(round(width*SS))), cv2.LINE_AA, shift=4)
        self.over(m.astype(np.float32)/255, x0, y0, color, alpha)

    # -- type -----------------------------------------------------------------------------
    def text(self, s, x, y, style, t, t_in, t_out=None, anim="letters", align="l", order="lr",
             vel=(0.0, 0.0), opacity=1.0, clamp=True, dur_in=None, glow=0.0, scrim=0.0, size_scale=1.0):
        """animated text block. (x, y) = anchor at 1x px on the baseline; align l/c/r.
        anim 'letters': per-letter opacity + blur + rise + tracking settle (stagger by `order`).
        anim 'wipe': soft-edged mask sweeping across the block (order 'lr' or 'center').
        Returns the 1x bbox (x0, y0, x1, y1) actually used (after clamping), or None."""
        st = TYPE[style]; k = self.k
        px = int(round(st["size"]*k*size_scale*SS))
        if t < t_in-0.05: return None
        dur_in = dur_in or (1.25 if anim == "letters" else 1.0)
        # tracking: settles from wider to the nominal value, then keeps a barely perceptible drift
        e_tr = out_expo(lin(t, t_in, t_in+2.2))
        track = st["track"]+(0.16 if anim == "letters" else 0.04)*(1-e_tr)+(0.004*max(t-t_in, 0) if style == "title" else 0.0)
        out_p = 0.0
        if t_out is not None:
            if t > t_out+0.9: return None
            out_p = lin(t, t_out, t_out+0.75)
            track += 0.08*in_cubic(out_p)
        xs, wtot = layout(s, px, st["weight"], st["italic"], track)
        # fit inside safe width
        sx0, sy0, sx1, sy1 = (v*SS for v in self.safe)
        maxw = sx1-sx0
        if wtot > maxw:
            return self.text(s, x, y, style, t, t_in, t_out, anim, align, order, vel, opacity, clamp,
                             dur_in, glow, scrim, size_scale*maxw/wtot*0.98)
        X = x*SS-(wtot/2 if align == "c" else wtot if align == "r" else 0.0)
        Y = y*SS
        asc, desc = px*0.78, px*0.26
        if clamp:
            X = min(max(X, sx0), sx1-wtot)
            Y = min(max(Y, sy0+asc), sy1-desc)
        # block buffer (alpha) -------------------------------------------------------------
        pad = int(px*0.6)+8
        bx0, by0 = int(math.floor(X))-pad, int(math.floor(Y-asc))-pad
        bw, bh = int(wtot)+2*pad+2, int(asc+desc)+2*pad+2
        buf = np.zeros((bh, bw), np.float32)
        n = len(s)
        for i, c in enumerate(s):
            g, (ox, oy) = glyph(c, px, st["weight"], st["italic"])
            if g is None: continue
            if order == "center": r = abs(i-(n-1)/2)/max((n-1)/2, 1)
            elif order == "rl": r = 1-i/max(n-1, 1)
            else: r = i/max(n-1, 1)
            a, blur, dy = 1.0, 0.0, 0.0
            if anim == "letters":
                stag = 0.55 if n > 6 else 0.3
                p = lin(t, t_in+r*stag, t_in+r*stag+dur_in*0.75)
                a = out_cubic(p); blur = (1-out_quart(p))*0.11*px; dy = (1-out_expo(p))*0.14*px
            if out_p > 0:
                po = lin(t, t_out+(1-r)*0.25, t_out+(1-r)*0.25+0.55)
                a *= 1-in_out_sine(po); blur += in_cubic(po)*0.09*px; dy -= in_cubic(po)*0.10*px
            if a <= 0.003: continue
            gx = X+xs[i]+ox-bx0; gy = Y+oy+dy-by0
            if blur > 0.35:
                gp = int(math.ceil(blur*2.5))
                g = cv2.GaussianBlur(np.pad(g, gp), (0, 0), blur); gx -= gp; gy -= gp
            ix, iy = int(math.floor(gx)), int(math.floor(gy)); fx, fy = gx-ix, gy-iy
            if fx > 1e-3 or fy > 1e-3:
                M = np.float32([[1, 0, fx], [0, 1, fy]])
                g = cv2.warpAffine(np.pad(g, ((0, 1), (0, 1))), M, (g.shape[1]+1, g.shape[0]+1), flags=cv2.INTER_LINEAR)
            h_, w_ = g.shape
            y0_, x0_ = max(iy, 0), max(ix, 0); y1_, x1_ = min(iy+h_, bh), min(ix+w_, bw)
            if y1_ <= y0_ or x1_ <= x0_: continue
            sub = buf[y0_:y1_, x0_:x1_]
            np.maximum(sub, g[y0_-iy:y1_-iy, x0_-ix:x1_-ix]*a, out=sub)
        if anim == "wipe":
            p = in_out_cubic(lin(t, t_in, t_in+dur_in))
            soft = 0.35*wtot+px
            cols = np.arange(bw, dtype=np.float32)+bx0
            if order == "center":
                d = np.abs(cols-(X+wtot/2)); edge = p*(wtot/2+soft)
                m = np.clip((edge-d)/soft, 0, 1)
            elif order == "rl":
                edge = X+wtot-p*(wtot+soft); m = np.clip((cols-edge)/soft, 0, 1)
            else:
                edge = X+p*(wtot+soft); m = np.clip((edge-cols)/soft, 0, 1)
            buf *= (m*m*(3-2*m))[None, :]
            buf *= out_cubic(lin(t, t_in, t_in+dur_in*0.6))
            if out_p > 0: buf *= 1-in_out_sine(out_p)
        # directional motion blur from the anchor's screen velocity (px per shutter at 1x)
        vx, vy = vel[0]*SS, vel[1]*SS; L = math.hypot(vx, vy)
        if L > 1.5:
            n_ = int(min(L, 60)); kern = np.zeros((2*n_+1, 2*n_+1), np.float32)
            cv2.line(kern, (n_-int(round(vx/2)), n_-int(round(vy/2))), (n_+int(round(vx/2)), n_+int(round(vy/2))), 1.0, 1, cv2.LINE_AA)
            kern /= kern.sum(); buf = cv2.filter2D(buf, -1, kern)
        self.over(buf, bx0, by0, INK, opacity)
        bb = ((X)/SS, (Y-asc)/SS, (X+wtot)/SS, (Y+desc)/SS)
        if glow > 0:
            g2 = cv2.resize(buf, (max(bw//(2*SS), 1), max(bh//(2*SS), 1)), interpolation=cv2.INTER_AREA)
            gx0, gy0 = bx0//(2*SS), by0//(2*SS)
            self._add_small(self.glow, g2[..., None]*GOLD*glow*opacity, gx0, gy0)
        if scrim > 0:
            # a very soft, wide darkening behind titles: reads like natural haze, not a box
            sc4 = cv2.resize(buf, (max(bw//(4*SS), 1), max(bh//(4*SS), 1)), interpolation=cv2.INTER_AREA)
            self._add_small(self.scrim, sc4*scrim*opacity, bx0//(4*SS), by0//(4*SS))
        return bb

    @staticmethod
    def _add_small(dst, src, x0, y0):
        h, w = src.shape[:2]
        X0, Y0 = max(x0, 0), max(y0, 0); X1, Y1 = min(x0+w, dst.shape[1]), min(y0+h, dst.shape[0])
        if X1 > X0 and Y1 > Y0: dst[Y0:Y1, X0:X1] += src[Y0-y0:Y1-y0, X0-x0:X1-x0]

    def rule(self, cx, y, half, alpha, width=1.2):
        """hairline growing symmetrically from the centre (1x px)"""
        if half < 1 or alpha <= 0.004: return
        n = 32; xs = np.linspace(cx-half, cx+half, n)
        u = np.linspace(-1, 1, n); al = alpha*np.clip(1.25-np.abs(u)**2, 0, 1)   # tapered ends
        self.stroke(np.stack([xs, np.full(n, y)], 1), width*self.k, al, INK, chunks=16)

    # -- final composite ---------------------------------------------------------------
    def composite(self, img):
        H, W = self.H, self.W; k = self.k
        ink = cv2.resize(self.ink, (W, H), interpolation=cv2.INTER_AREA)
        a = ink[..., 3]
        # soft shadow (slightly below) + very wide scrim: legibility on bright reef and sand
        sh = cv2.GaussianBlur(a, (0, 0), 3.2*k)
        sh = np.roll(sh, int(round(1.5*k)), axis=0)
        sh2 = cv2.GaussianBlur(cv2.resize(a, (W//4, H//4), interpolation=cv2.INTER_AREA), (0, 0), 3.0*k)
        sh2 = cv2.resize(sh2, (W, H), interpolation=cv2.INTER_LINEAR)
        scr = cv2.GaussianBlur(self.scrim, (0, 0), 14*k) if self.scrim.any() else None
        dark = 0.50*np.clip(sh*1.5, 0, 1)+0.16*np.clip(sh2*2.0, 0, 1)
        if scr is not None:
            dark = dark+0.20*np.clip(cv2.resize(scr, (W, H), interpolation=cv2.INTER_LINEAR)*1.4, 0, 1)
        img = img*(1-np.clip(dark, 0, 0.62))[..., None]
        # glow: two radii, screen-blended (never clips harshly)
        if self.glow.any():
            g1 = cv2.GaussianBlur(self.glow, (0, 0), 2.6*k); g2 = cv2.GaussianBlur(self.glow, (0, 0), 11*k)
            g = cv2.resize(0.75*g1+0.55*g2, (W, H), interpolation=cv2.INTER_LINEAR)
            img = 1-(1-img)*(1-np.clip(g, 0, 1))
        # ink over
        img = img*(1-a[..., None])+ink[..., :3]
        return np.clip(img, 0, 1).astype(np.float32)

# ------------------------------------------------------------------ geometry helpers
def _arc3d(a, b, lift=0.055, n=220):
    A = ecef(a[1], a[0]); B = ecef(b[1], b[0]); A, B = A/np.linalg.norm(A), B/np.linalg.norm(B)
    om = math.acos(float(np.clip(A@B, -1, 1))); s = np.linspace(0, 1, n)
    P = (np.sin((1-s)*om)[:, None]*A+np.sin(s*om)[:, None]*B)/math.sin(om)
    h = lift*om*R_E*np.sin(np.pi*s)
    return P*(R_E+h)[:, None]

ARC_SIN = _arc3d(PLACES["changi"], PLACES["tjq"])
ARC_CGK = _arc3d(PLACES["cgk"], PLACES["tjq"])

def _route3d(n=200, bow=450.0):
    """gentle curve over open water, Teluk Gembira jetty -> Pulau Seliu village jetty (indicative)"""
    ax, ay = xy(*PLACES["teluk_gembira_pier"]); bx, by = xy(*PLACES["seliu_landing"])
    mx, my = (ax+bx)/2, (ay+by)/2; nx, ny = -(by-ay), (bx-ax); L = math.hypot(nx, ny)
    cx, cy = mx+nx/L*bow, my+ny/L*bow
    s = np.linspace(0, 1, n)
    X = (1-s)**2*ax+2*(1-s)*s*cx+s**2*bx; Y = (1-s)**2*ay+2*(1-s)*s*cy+s**2*by
    lo, la = lonlat(X, Y)
    return ecef(np.asarray(la), np.asarray(lo), 4.0)

ROUTE = _route3d()

def _outline3d():
    d = json.load(open(os.path.join(ROOT, "data", "seliu_outline_lonlat.json")))
    ll = np.array(d["lonlat"], np.float64)
    P = ecef(ll[:, 1], ll[:, 0], 2.0)
    P = np.vstack([P, P[:1]])                              # closed
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1); s = np.r_[0, np.cumsum(seg)]
    return P, s/s[-1]

OUTLINE, OUTLINE_S = _outline3d()

def ground(key, h=0.0):
    lon, lat = PLACES[key]; return ecef(lat, lon, h)

class Proj:
    """projection through the plate camera, rescaled to the image size if needed"""
    def __init__(self, cam, W, H):
        self.cam = cam; self.sx = W/cam.W; self.sy = H/cam.H; self.W, self.H = W, H
    def __call__(self, P):
        p, z = self.cam.project(np.asarray(P, np.float64))
        p = p*[self.sx, self.sy]
        ok = (z > 0)
        if hasattr(self.cam, "visible"): ok = ok & self.cam.visible(np.asarray(P, np.float64))
        return p, ok

def edge_fade(p, W, H, m=0.04):
    fx = min(p[0]/W, 1-p[0]/W)/m; fy = min(p[1]/H, 1-p[1]/H)/m
    return clamp01(min(fx, fy))

def _partial(p, s, u0, u1):
    """sub-polyline of screen points p (param s in 0..1) between u0 < u1, with exact end points"""
    if u1 <= u0: return None, None
    i0 = int(np.searchsorted(s, u0)); i1 = int(np.searchsorted(s, u1))
    def at(u):
        j = int(np.clip(np.searchsorted(s, u), 1, len(s)-1)); w = (u-s[j-1])/max(s[j]-s[j-1], 1e-12)
        return p[j-1]*(1-w)+p[j]*w
    q = np.vstack([at(u0)[None], p[i0:i1], at(u1)[None]]); su = np.r_[u0, s[i0:i1], u1]
    return q, su

# ------------------------------------------------------------------ the graphics
def _flight(cv, proj, P3, t, t0, t1, out0, out1, vel_dt):
    s = np.linspace(0, 1, len(P3))
    p, ok = proj(P3)
    if not ok.all(): return
    u = in_out_cubic(lin(t, t0, t1))                      # plane-like: accelerate, cruise, settle
    if u <= 0: return
    tail = in_out_cubic(lin(t, out0, out1))               # erase from the origin: the line flows into Belitung
    if tail >= u-1e-3: return
    q, su = _partial(p, s, tail, u)
    # trail: brighter near the head, settling to a calm base; fades at the very start
    al = 0.62+0.38*np.exp(-(u-su)/0.16)
    al *= np.clip((su-tail)/0.06+0.15, 0, 1)
    fade_all = 1-smooth(lin(t, out0+0.5*(out1-out0), out1))
    cv.stroke(q, GEOM["line"]*cv.k, al*0.92*fade_all)
    cv.glow_poly(q, 3.0*cv.k, GOLD, 0.10*fade_all)
    if u < 1:
        head = q[-1]
        # comet: a short streak (the head's motion blur) and a warm bloom
        hs, _ = _partial(p, s, max(tail, u-0.05), u)
        cv.glow_poly(hs, 5*cv.k, GOLD, 0.55)
        cv.glow_dot(head, 7*cv.k, GOLD, 0.9)
        cv.disc(head, 3.6*cv.k, 1.0, INK)

def _dot(cv, p, t, t0, alpha=1.0, r=None, ring=True):
    """a place dot: grows in (out-cubic) with one thin ring ping, no bounce"""
    if t < t0: return
    r = (r or GEOM["dot"])*cv.k
    e = out_cubic(lin(t, t0, t0+0.45))
    cv.disc(p, r*(0.35+0.65*e), alpha*e, INK)
    cv.glow_dot(p, r*1.6, GOLD, 0.35*alpha*e)
    if ring:
        q = lin(t, t0+0.05, t0+1.1)
        if 0 < q < 1:
            cv.ring(p, r*(1.2+4.2*out_cubic(q)), GEOM["ring"]*cv.k, alpha*0.7*(1-q)**1.5, INK)

def measure(cv, s, style):
    st = TYPE[style]; px = int(round(st["size"]*cv.k*SS))
    return layout(s, px, st["weight"], st["italic"], st["track"])[1]/SS

def _side_label(cv, name, p, t, t_in, t_out, vel, opacity, p_ref=None):
    """place label to the right of its dot. Near the frame edge it may slide inward a little
    (never onto the dot); if that is not enough it moves under the dot, centred and clamped.
    The choice is made from p_ref (the dot at the end of its shot) so the label never jumps mid-shot."""
    k = cv.k; w = measure(cv, name, "place")*1.04          # margin for the entry tracking
    pr = p if p_ref is None else p_ref
    over = pr[0]+20*k+w-cv.safe[2]
    if over <= 12*k:
        cv.text(name, p[0]+20*k-max(over, 0), p[1]+13*k, "place", t, t_in, t_out, vel=vel, opacity=opacity, clamp=False)
    else:
        cv.text(name, p[0], p[1]+50*k, "place", t, t_in, t_out, align="c", order="center", vel=vel, opacity=opacity)

def _velocity(proj_fn, t, dt=0.02):
    """screen motion (px) of an anchor during a 180-degree shutter (1/50 s)"""
    a = proj_fn(t-dt/2); b = proj_fn(t+dt/2)
    if a is None or b is None: return (0.0, 0.0)
    return (float(b[0]-a[0]), float(b[1]-a[1]))

def draw(img, t, cam, fmt="16x9", cam_at=None):
    """render all graphics for time t over img (float32 HxWx3, 0..1).
    cam: render.Camera of this frame. cam_at: optional callable t -> Camera, used only to measure
    screen velocity for motion blur (if None, velocity is estimated from timeline.camera)."""
    H, W = img.shape[:2]
    V = fmt == "9x16"
    cv = Canvas(W, H, fmt); k = cv.k
    proj = Proj(cam, W, H)
    if cam_at is None:
        cam_at = _timeline_cam(fmt, cam)

    def anchor_at(key, h=0.0):
        def f(tt):
            c = cam_at(tt)
            if c is None: return None
            p, ok = Proj(c, W, H)(ground(key, h)); return p if ok else None
        return f

    def place(key):
        p, ok = proj(ground(key)); return (p, bool(ok))

    # ================= REGION: flights (2.3 - 9.3 s) =================================
    r_out0, r_out1 = T["region_out"]
    if T.get("region_in", 2.0) < t < r_out1+0.6:
        fade_region = 1-smooth(lin(t, r_out0+0.3, r_out1))
        _flight(cv, proj, ARC_SIN, t, *T["arc_sin"], r_out0, r_out1-0.1, 0)
        _flight(cv, proj, ARC_CGK, t, *T["arc_cgk"], r_out0+0.15, r_out1, 0)
        for key, name, td, tl in (("changi", "SINGAPORE", T["sin_dot"], T["sin_label"]),
                                  ("cgk", "JAKARTA", T["cgk_dot"], T["cgk_label"])):
            p, ok = place(key)
            if not ok: continue
            ef = edge_fade(p, W, H) * fade_region
            if ef <= 0.01: continue
            _dot(cv, p, t, td, ef)
            vel = _velocity(anchor_at(key), t)
            if V: cv.text(name, p[0], p[1]+50*k, "place", t, tl, r_out0+0.2, align="c", vel=vel, opacity=ef)
            else: _side_label(cv, name, p, t, tl, r_out0+0.2, vel, ef)
        # arrival on Belitung (Tanjung Pandan, not named)
        p, ok = place("tjq")
        if ok:
            ef = edge_fade(p, W, H)*fade_region
            _dot(cv, p, t, T["tjq_arrive"], ef, r=GEOM["dot"]*0.9)
            if t > T["arc_cgk"][1]:
                q = lin(t, T["arc_cgk"][1], T["arc_cgk"][1]+0.9)    # second arrival: a softer glint
                if 0 < q < 1: cv.ring(p, (6+18*out_cubic(q))*k, GEOM["ring"]*k, 0.5*(1-q)**1.5*ef, INK)
            pb, okb = place("belitung_centre")
            if okb:
                vel = _velocity(anchor_at("belitung_centre"), t)
                cv.text("BELITUNG", pb[0]+26*k, pb[1]+14*k, "place", t, T["bel_small"], r_out1-0.55,
                        vel=vel, opacity=edge_fade(pb, W, H))
        # note on the Singapore arc, placed beside its middle, on the open-sea side
        if t > T["flights_note"]-0.1:
            p, ok = proj(ARC_SIN[len(ARC_SIN)//2])
            if ok:
                if V: cv.text("Direct flights", p[0]+30*k, p[1]-10*k, "note", t, T["flights_note"], r_out0, anim="wipe", opacity=edge_fade(p, W, H))
                else: cv.text("Direct flights", p[0]+30*k, p[1]+6*k, "note", t, T["flights_note"], r_out0, anim="wipe", opacity=edge_fade(p, W, H))

    # ================= BELITUNG title (10.4 - 13.8 s) ===================================
    tb, to = T["bel_title"], T["bel_out"]
    if tb-0.1 < t < to+1.0:
        # floats above the island at parallax 0.45 relative to the ground (a layer nearer the lens)
        tref = T.get("bel_ref", 11.8)
        f = anchor_at("belitung_centre")
        p_now, p_ref = f(t), f(tref)
        if p_now is not None and p_ref is not None:
            c = np.array([W/2, H*(0.44 if not V else 0.40)])
            base = 0.55*p_ref+0.45*c
            pos = base+0.45*(p_now-p_ref)
            if V: pos[0] = W/2                                 # vertical: always centred
            vel = tuple(0.45*np.array(_velocity(f, t)))
            bb = cv.text("BELITUNG", pos[0], pos[1], "title", t, tb, to, align="c", order="center",
                         vel=vel, glow=0.10, scrim=0.8)
            if bb:
                cxm = (bb[0]+bb[2])/2; yr = bb[3]+20*k
                gw = out_expo(lin(t, T["bel_rule"], T["bel_rule"]+1.1))*(1-in_out_sine(lin(t, to, to+0.6)))
                cv.rule(cxm, yr, gw*min(150*k, (bb[2]-bb[0])*0.18), 0.75*gw)
                cv.text("BANGKA BELITUNG ISLANDS  ·  INDONESIA", cxm, yr+46*k, "subtitle", t, T["bel_sub"], to+0.05,
                        anim="wipe", align="c", order="center", vel=vel, dur_in=1.1, scrim=0.6)

    # ================= SELIU (15.9 s -> end) =============================================
    o0, o1 = T["outline"]
    if t > o0:
        p, ok = proj(OUTLINE)
        if ok.mean() > 0.98:
            s = OUTLINE_S
            u = in_out_cubic(lin(t, o0, o1))*0.5              # two heads, from the village jetty, both ways
            flash = math.exp(-max(t-T["outline_flash"], 0)/0.9) if t >= T["outline_flash"] else 0.0
            settle = smooth(lin(t, T["outline_flash"]+0.3, T["outline_flash"]+2.6))
            line_a = (1.0-0.42*settle)                         # settles to a delicate 0.58
            glow_a = 0.42+0.75*flash-0.22*settle
            if u > 0:
                for a_, b_ in ((0.0, u), (1-u, 1.0)):
                    q, su = _partial(p, s, a_, b_)
                    if q is None: continue
                    head_s = b_ if a_ == 0.0 else a_
                    al = line_a*(0.72+0.28*np.exp(-np.abs(head_s-su)/0.05)) if u < 0.5 else np.full(len(su), line_a)
                    wl = GEOM["outline"]*(1-0.22*settle)*k
                    cv.stroke(q, wl+2.0*k, al*(0.26-0.10*settle), UNDER, chunks=40)   # separation from the sand
                    cv.stroke(q, wl, al, SHORE, chunks=40)
                    cv.glow_poly(q, 3.5*k, GOLD, glow_a)
                    if u < 0.5:
                        hp = q[-1] if a_ == 0.0 else q[0]
                        hs, _ = _partial(p, s, max(0.0, b_-0.03), b_) if a_ == 0.0 else _partial(p, s, a_, min(1.0, a_+0.03))
                        if hs is not None: cv.glow_poly(hs, 6*k, GOLD, 0.7)
                        cv.glow_dot(hp, 8*k, GOLD, 1.0)
                        cv.disc(hp, 3.0*k, 1.0, INK)
            # arrival glint: one soft light running the coast both ways from the jetty, once
            g0, g1 = T["glint"]
            if g0 < t < g1:
                gu = in_out_sine(lin(t, g0, g1))*0.5; ga = math.sin(math.pi*lin(t, g0, g1))
                for a_, b_ in ((max(0.0, gu-0.06), gu), (1-gu, min(1.0, 1-gu+0.06))):
                    q, su = _partial(p, s, a_, b_)
                    if q is not None:
                        cv.glow_poly(q, 5*k, GOLD, 0.45*ga)
                        cv.stroke(q, GEOM["outline"]*k, 0.45*ga, INK, chunks=4)

    # SELIU ISLAND: floats in the haze above the island's north coast, slight parallax
    ts = T["seliu_title"]
    if t > ts-0.1:
        def title_anchor(tt):
            c = cam_at(tt)
            if c is None: return None
            pp, ok = Proj(c, W, H)(OUTLINE)
            if ok.mean() < 0.98: return None
            ctr = pp.mean(0)
            return np.array([ctr[0], pp[:, 1].min()]) if not V else np.array([W/2, pp[:, 1].min()])
        a_now, a_ref = title_anchor(t), title_anchor(T.get("seliu_ref", 22.0))
        if a_now is not None and a_ref is not None:
            pos = a_ref+0.75*(a_now-a_ref)                   # 0.75: a layer slightly above the ground
            gap = (150 if not V else 190)*k
            vel = tuple(0.75*np.array(_velocity(title_anchor, t)))
            bb = cv.text("SELIU ISLAND", pos[0], pos[1]-gap, "title", t, ts, None, align="c", order="center",
                         vel=vel, glow=0.12, scrim=0.8)
            if bb:
                cxm = (bb[0]+bb[2])/2
                cv.text("OFF THE SOUTH-WEST COAST OF BELITUNG", cxm, bb[3]+50*k, "subtitle", t, T["seliu_sub"], None,
                        anim="wipe", align="c", order="center", vel=vel, dur_in=1.1, scrim=0.6)

    # Teluk Gembira, the crossing, the arrival
    if t > T["tg_dot"]:
        p, ok = place("teluk_gembira_pier")
        if ok:
            ef = edge_fade(p, W, H)
            _dot(cv, p, t, T["tg_dot"], ef)
            vel = _velocity(anchor_at("teluk_gembira_pier"), t)
            if V: cv.text("TELUK GEMBIRA", p[0], p[1]+56*k, "place", t, T["tg_label"], None, align="c", vel=vel, opacity=ef)
            else: _side_label(cv, "TELUK GEMBIRA", p, t, T["tg_label"], None, vel, ef,
                              p_ref=anchor_at("teluk_gembira_pier")(T.get("tg_ref", 24.96)))
    r0, r1 = T["route"]
    if t > r0:
        p, ok = proj(ROUTE)
        if ok.all():
            s = np.linspace(0, 1, len(ROUTE))
            u = in_out_sine(lin(t, r0, r1))                    # a boat: steady, no rush
            q, su = _partial(p, s, 0.0, u)
            if q is not None:
                al = 0.70+0.30*np.exp(-(u-su)/0.12)
                cv.stroke(q, GEOM["route"]*k, al*0.95, LINE)
                cv.glow_poly(q, 3*k, GOLD, 0.10)
                if u < 1:
                    hs, _ = _partial(p, s, max(0.0, u-0.06), u)
                    cv.glow_poly(hs, 5*k, GOLD, 0.45)          # soft wake behind the head
                    cv.glow_dot(q[-1], 6*k, GOLD, 0.8)
                    cv.disc(q[-1], 3.4*k, 1.0, INK)
            if t > T["boat_note"]-0.1:
                m = p[int(0.40*(len(p)-1))]                  # 40% from Teluk Gembira: clear of Seliu's sand tip
                if V: cv.text("15–20 min by boat", m[0]+28*k, m[1]+14*k, "note", t, T["boat_note"], None, anim="wipe", order="rl")
                else: cv.text("15–20 min by boat", m[0], m[1]-26*k, "note", t, T["boat_note"], None, anim="wipe", align="c", order="rl")
            _dot(cv, p[-1], t, T["jetty"], 0.95, r=GEOM["dot"]*0.8)

    return cv.composite(np.asarray(img, np.float32))


_TL_CACHE = {}
def _timeline_cam(fmt, cam):
    """camera(t) from tools/timeline.py for the right format, only to measure screen velocity"""
    if fmt not in _TL_CACHE:
        import importlib.util
        spec = importlib.util.spec_from_file_location(f"_tl_{fmt}", os.path.join(os.path.dirname(os.path.abspath(__file__)), "timeline.py"))
        old = os.environ.get("SELIU_FMT"); old_shot = os.environ.pop("SELIU_SHOT", None)
        os.environ["SELIU_FMT"] = fmt
        try:
            mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        finally:
            if old is None: os.environ.pop("SELIU_FMT", None)
            else: os.environ["SELIU_FMT"] = old
            if old_shot is not None: os.environ["SELIU_SHOT"] = old_shot
        _TL_CACHE[fmt] = mod
    mod = _TL_CACHE[fmt]
    from render import Camera
    def f(tt):
        return Camera(*mod.camera(tt), vfov=mod.VFOV, W=cam.W, H=cam.H)
    return f
