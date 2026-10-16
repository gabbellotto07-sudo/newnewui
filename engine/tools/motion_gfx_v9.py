"""Seliu v9 — motion graphics. Replaces the v6/v8 system (letters flying in with blur, pings, dots, white lines,
fixed GIS outline). One gesture per role, nothing else:
    titles      A: mask reveal (the word rises out of an invisible edge) + a fine gold rule that draws itself
                B: dissolve of light (a soft warm glow condenses into the letters)
    places      a plain fade
    notes       italic, a soft wipe (left -> right; the boat note follows the boat, right -> left)
No letter-by-letter animation, no bounce, overshoot or scale pop.

Lines are light in the scene, not UI:
    flights     3D great-circle arcs that really rise above the globe; a luminous head, a tail that fades
                behind it and drains into Belitung on arrival; width follows depth
    crossing    a thin luminous wake on the sea, in perspective, widening and dying behind the head
    Seliu       one light runs the real coastline once and is gone; what stays is the light on the island
                (the renderer's matte), never a line

Two directions (env SELIU_GFX):
    A "Documentario": titles bottom-left, left aligned, gold rule; minimal place names near their anchors
    B "Nel mondo":    titles, places and notes laid on the sea / ground plane through the plate camera
                      (perspective, fixed in the world so they move with the territory), veiled by distance
                      like the sea, a faint shadow under the real sun, the softness of distance

    draw(img, t, cam, fmt="16x9", cam_at=None) -> img       (img float32 HxWx3 0..1, graded plate)
Data: only the approved texts and coordinates (geo.PLACES); the airport is never named.
"""
import os, sys, json, math
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import motion_gfx as M
from motion_gfx import (Canvas, glyph, layout, INK, GOLD, SS, lin, smooth, out_cubic, out_quart, in_out_cubic,
                        in_out_sine, clamp01, _partial, Proj, edge_fade, OUTLINE, OUTLINE_S)
from geo import PLACES, xy, lonlat
from render import ecef, enu_basis, R_E

STYLE = os.environ.get("SELIU_GFX", "A").upper()
RULE = np.array([0.93, 0.80, 0.55], np.float32)          # fine gold rule (A)
SUN_AZ, SUN_EL = 46.0, 57.5

# ------------------------------------------------------------------ type (px at 1080 short side)
# v8: place 36, note 42, subtitle 34 caps. v9: +33 % or more for the phone; subtitles become italic sentences
TYPE = {
    "title": dict(size=88, weight=380, italic=False, track=0.30),
    "sub":   dict(size=54, weight=440, italic=True,  track=0.015),     # +45 % on the v8 subtitle (34) and more
    "place": dict(size=52, weight=520, italic=False, track=0.16),      # +45 % (v8 36)
    "note":  dict(size=61, weight=420, italic=True,  track=0.015),     # +45 % (v8 42)
}
SCALE = float(os.environ.get("SELIU_TYPE_SCALE", "1.0"))  # phone test: 1.0 = +33 %, 1.09 = +45 % on places/notes

# ------------------------------------------------------------------ timing (28 s, 25 fps)
T = dict(
    sin_label=4.0, cgk_label=4.4, labels_out=8.45,
    arc_sin=(4.30, 7.50), arc_cgk=(4.80, 8.00), drain=0.9,
    flights_note=(5.15, 8.45),
    bel_title=(10.30, 13.40), bel_sub=(11.05, 13.40),
    coast=(17.85, 20.25),
    seliu_title=18.45, seliu_sub=(19.25, 24.70),
    tg=(20.55, 24.70), wake=(21.15, 23.95), wake_out=(24.40, 27.70), boat_note=(21.85, 24.70),
)
OUT = 0.8                                                 # every exit: a plain fade of 0.8 s

# sound touches for sound_v9 (very small, under everything)
SOUND_CUES = []                                           # v9: no touches under the titles (the reviewer heard a click)

# ------------------------------------------------------------------ text as an alpha block
def text_block(s, style, k, scale=1.0):
    """alpha (SS px) of a whole line, static, kerning-aware. -> a, asc, desc, width (SS px)"""
    st = TYPE[style]
    sc = scale*(SCALE if style in ("place", "note", "sub") else 1.0)
    px = int(round(st["size"]*k*sc*SS))
    xs, wtot = layout(s, px, st["weight"], st["italic"], st["track"])
    asc, desc = int(px*0.80), int(px*0.28)
    pad = int(px*0.25)+4
    W, H = int(wtot)+2*pad+int(px*0.2), asc+desc+2*pad
    a = np.zeros((H, W), np.float32)
    for i, c in enumerate(s):
        g, (ox, oy) = glyph(c, px, st["weight"], st["italic"])
        if g is None: continue
        gx, gy = pad+xs[i]+ox, pad+asc+oy
        ix, iy = int(math.floor(gx)), int(math.floor(gy)); fx, fy = gx-ix, gy-iy
        if fx > 1e-3 or fy > 1e-3:
            Mt = np.float32([[1, 0, fx], [0, 1, fy]])
            g = cv2.warpAffine(np.pad(g, ((0, 1), (0, 1))), Mt, (g.shape[1]+1, g.shape[0]+1), flags=cv2.INTER_LINEAR)
        h_, w_ = g.shape
        y0, x0 = max(iy, 0), max(ix, 0); y1, x1 = min(iy+h_, H), min(ix+w_, W)
        if y1 > y0 and x1 > x0:
            np.maximum(a[y0:y1, x0:x1], g[y0-iy:y1-iy, x0-ix:x1-ix], out=a[y0:y1, x0:x1])
    return a, pad, asc, desc, wtot

def presence(t, t_in, t_out, dur):
    """0..1 entry progress and exit multiplier"""
    p = lin(t, t_in, t_in+dur)
    o = 1.0 if t_out is None else 1-smooth(lin(t, t_out, t_out+OUT))
    return p, o

def g_fade(a, p):
    return a*smooth(p)

def g_wipe(a, p, pad, w, rtl=False):
    """soft-edged wipe across the line"""
    H, W = a.shape
    e = in_out_cubic(p); soft = 0.30*w+20
    cols = np.arange(W, dtype=np.float32)-pad
    m = np.clip(((w+soft)*e-cols)/soft, 0, 1) if not rtl else np.clip((cols-(w-(w+soft)*e))/soft, 0, 1)
    return a*(m*m*(3-2*m))[None, :]*smooth(lin(p, 0, 0.35))

def g_mask(a, p, pad, asc, desc):
    """the line rises out of an invisible edge just under its baseline (documentary title reveal)"""
    H, W = a.shape
    e = out_cubic(p)                                    # decelerates, settles, never overshoots
    dy = (1-e)*(asc+desc)*0.92
    sh = np.zeros_like(a)
    d = int(round(dy))
    if d < H: sh[d:] = a[:H-d]
    edge = pad+asc+desc                                  # rows below this are hidden
    sh[edge:] = 0
    soft = max(2, int((asc+desc)*0.06))
    sh[edge-soft:edge] *= np.linspace(1, 0, soft)[:, None]
    return sh*smooth(lin(p, 0, 0.25))

# ------------------------------------------------------------------ screen-space text (A)
def put(cv, a, x, y, pad, asc, opacity=1.0, color=INK, glow=0.0):
    """place block a (SS) with its baseline-left at screen (x, y) (1x px)"""
    if opacity <= 0.003: return
    x0 = int(round(x*SS))-pad; y0 = int(round(y*SS))-pad-asc
    cv.over(a, x0, y0, color, opacity)
    if glow > 0:
        g2 = cv2.resize(a, (max(a.shape[1]//(2*SS), 1), max(a.shape[0]//(2*SS), 1)), interpolation=cv2.INTER_AREA)
        cv._add_small(cv.glow, g2[..., None]*GOLD*glow*opacity, x0//(2*SS), y0//(2*SS))

def title_A(cv, t, name, sub, t_in, sub_in, t_out, sub_out):
    """bottom-left title: gold rule draws itself left -> right, the word rises out of its edge, then the
    italic line wipes in under it"""
    k = cv.k; W, H = cv.W, cv.H
    V = cv.fmt == "9x16"
    x = (0.075 if V else 0.062)*W
    # 16:9 bottom-left; 9:16 top-left (in the vertical frame the crossing runs bottom -> top and the phone UI
    # owns the bottom): the title sits on the far sea, under the top safe margin
    y = (0.205 if V else 0.835)*H                       # title baseline
    a, pad, asc, desc, w = text_block(name, "title", k, 0.78 if V else 1.0)
    p, o = presence(t, t_in, t_out, 1.25)
    if p > 0 and o > 0:
        put(cv, g_mask(a, p, pad, asc, desc), x, y, pad, asc, o, glow=0.05)
        # the rule: above the title, from the left margin, drawn in 1.1 s from 0.2 s before the word
        r = out_quart(lin(t, t_in-0.2, t_in+0.9))
        L = min(w/SS*0.62, 340*k)*r
        if L > 1:
            yr = y-asc/SS-30*k
            n = 24; xs = np.linspace(x, x+L, n)
            al = np.clip(1.15-np.linspace(0, 1, n)**3, 0, 1)*0.85*o       # thinning, fading toward its tip
            cv.stroke(np.stack([xs, np.full(n, yr)], 1), 1.9*k, al, RULE, chunks=12)
            cv.glow_poly(np.stack([xs, np.full(n, yr)], 1), 2.5*k, GOLD, 0.16*o)
    if sub:
        b, pb, ab, db, wb = text_block(sub, "sub", k, 0.86 if V else 1.0)
        ps, os_ = presence(t, sub_in, sub_out, 1.1)
        if ps > 0 and os_ > 0:
            put(cv, g_wipe(b, ps, pb, wb), x+2*k, y+(58 if not V else 56)*k, pb, ab, os_*0.96)

def label_A(cv, s, p_scr, t, t_in, t_out, side="r", style="place", gesture="fade", opacity=1.0, rtl=False, dx=0.0, dy=0.0):
    """minimal label beside an anchor; stays inside the safe area"""
    k = cv.k
    a, pad, asc, desc, w = text_block(s, style, k)
    p, o = presence(t, t_in, t_out, 0.9 if gesture == "fade" else 1.2)
    if p <= 0 or o <= 0: return
    ww = w/SS
    if side == "r": x = p_scr[0]+18*k
    elif side == "l": x = p_scr[0]-18*k-ww
    else: x = p_scr[0]-ww/2
    y = p_scr[1]+asc/SS*0.38
    x += dx; y += dy
    sx0, sy0, sx1, sy1 = cv.safe
    x = min(max(x, sx0), sx1-ww); y = min(max(y, sy0+asc/SS), sy1-desc/SS)
    b = g_fade(a, p) if gesture == "fade" else g_wipe(a, p, pad, w, rtl)
    put(cv, b, x, y, pad, asc, o*opacity)

# ------------------------------------------------------------------ world text (B)
def _tangent(lat, lon):
    e, n, u = enu_basis(lat, lon); return e, n, u

def world_layer(img, cam, a, pad, asc, desc, w, anchor_ll, off_en, height_m, heading, op, light=0.0, lift=0.06,
                shadow=0.30, legible=0.35):
    """lay the alpha block a (SS px) on the local horizontal plane at anchor (lon, lat) + (east, north) offset (m).
    height_m: cap height in metres. heading: text baseline faces this view heading (deg). Returns img."""
    if op <= 0.003: return img
    H, W = img.shape[:2]
    lon0, lat0 = anchor_ll
    e, n, u = _tangent(lat0, lon0)
    C = ecef(lat0, lon0)+off_en[0]*e+off_en[1]*n
    hd = math.radians(heading)
    rgt = math.cos(hd)*e-math.sin(hd)*n                  # text right
    fwd = math.sin(hd)*e+math.cos(hd)*n                  # text up = away from the camera
    mpp = height_m/max(asc, 1)                           # metres per texture px
    Ht, Wt = a.shape
    cx, cy = pad+w/2, pad+asc                            # texture point at the anchor: baseline centre
    def corners(h):
        P = []
        for (tx, ty) in ((0, 0), (Wt, 0), (Wt, Ht), (0, Ht)):
            P.append(C+(tx-cx)*mpp*rgt+(cy-ty)*mpp*fwd+h*u)
        return np.array(P)
    lift_m = lift*height_m
    P = corners(lift_m)
    proj = Proj(cam, W, H)
    q, ok = proj(P)
    if not np.all(ok): return img
    v = P-cam.pos; dist = np.linalg.norm(v, axis=1)
    # pre-filter the texture to about twice its on-screen size, then warp with the true homography
    scr_h = max(np.linalg.norm(q[3]-q[0]), np.linalg.norm(q[2]-q[1]), 1.0)
    f = float(np.clip(2.0*scr_h/Ht, 0.02, 1.0))
    def warp(tex, Q):
        if f < 1: tex_s = cv2.resize(tex, (max(int(Wt*f), 2), max(int(Ht*f), 2)), interpolation=cv2.INTER_AREA)
        else: tex_s = tex
        hs, ws = tex_s.shape[:2]
        src = np.float32([[0, 0], [ws, 0], [ws, hs], [0, hs]])
        Mh = cv2.getPerspectiveTransform(src, np.float32(Q))
        return cv2.warpPerspective(tex_s, Mh, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    # depth ramp across the block (bilinear of the corner distances) -> distance haze and softness
    ramp = np.array([[dist[0], dist[1]], [dist[3], dist[2]]], np.float32)
    ramp = cv2.resize(ramp, (Wt, Ht), interpolation=cv2.INTER_LINEAR)
    al = warp(a, q)
    if al.max() <= 1e-3: return img
    dd = warp(ramp, q)
    dnear = float(dist.min())
    rel = np.clip((dd-dnear)/max(dnear, 1.0), 0, 1)
    # softness of distance: a far edge a touch softer (no lens blur: there is none at these distances)
    alb = cv2.GaussianBlur(al, (0, 0), 1.1)
    al = al*(1-rel*0.6)+alb*(rel*0.6)
    haze = 0.10+0.45*rel                                  # veiled like the sea behind it
    # shadow on the water under the real sun (letters floating a few % of their height above it)
    if shadow > 0 and lift_m > 0:
        off = lift_m/math.tan(math.radians(SUN_EL))
        az = math.radians(SUN_AZ)
        sdir = -(math.sin(az)*e+math.cos(az)*n)           # away from the sun
        qs, oks = proj(corners(0.0)+off*sdir)
        if np.all(oks):
            sa = cv2.GaussianBlur(warp(a, qs), (0, 0), 2.0)
            img = img*(1-shadow*op*sa)[..., None]
    # legibility: a very soft darkening around the letters (like the haze shadow of A)
    if legible > 0:
        dk = cv2.GaussianBlur(al, (0, 0), 6.0)
        img = img*(1-np.clip(legible*op*dk*1.6, 0, 0.45))[..., None]
    hz_col = np.array([0.78, 0.84, 0.90], np.float32)
    col = INK[None, None, :]*(1-haze[..., None])+hz_col*haze[..., None]
    A_ = np.clip(al*op, 0, 1)[..., None]
    img = img*(1-A_)+col*A_*(1-0.15*haze[..., None])+img*A_*0.15*haze[..., None]
    if light > 0:                                         # the dissolve of light: warm, soft, additive
        g = cv2.GaussianBlur(al, (0, 0), 7.0)*light
        img = 1-(1-img)*(1-np.clip(g[..., None]*GOLD, 0, 1))
    return np.clip(img, 0, 1)

def world_text(img, cam, s, style, anchor_ll, off_en, height_m, heading, t, t_in, t_out, gesture, k=1.0, rtl=False):
    a, pad, asc, desc, w = text_block(s, style, 2.2)     # crisp texture (~190 px caps for titles)
    dur = {"light": 1.8, "fade": 0.9, "wipe": 1.3}[gesture]
    p, o = presence(t, t_in, t_out, dur)
    if p <= 0 or o <= 0: return img
    light = 0.0
    if gesture == "light":
        b = a*smooth(lin(p, 0.25, 1.0)); light = 0.55*math.sin(math.pi*clamp01(p))*o
        b = np.maximum(b, cv2.GaussianBlur(a, (0, 0), 6)*0.5*smooth(lin(p, 0, 0.35))*(1-smooth(lin(p, 0.4, 1.0))))
    elif gesture == "wipe": b = g_wipe(a, p, pad, w, rtl)
    else: b = g_fade(a, p)
    return world_layer(img, cam, b, pad, asc, desc, w, anchor_ll, off_en, height_m, heading, o, light=light)

# ------------------------------------------------------------------ flights: arcs of light
def _arc3d(a, b, lift=0.085, n=260):
    A = ecef(a[1], a[0]); B = ecef(b[1], b[0]); A, B = A/np.linalg.norm(A), B/np.linalg.norm(B)
    om = math.acos(float(np.clip(A@B, -1, 1))); s = np.linspace(0, 1, n)
    P = (np.sin((1-s)*om)[:, None]*A+np.sin(s*om)[:, None]*B)/math.sin(om)
    h = lift*om*R_E*np.sin(np.pi*s)
    return P*(R_E+h)[:, None]

ARC_SIN = _arc3d(PLACES["changi"], PLACES["tjq"])
ARC_CGK = _arc3d(PLACES["cgk"], PLACES["tjq"])

def flight(cv, cam, P3, t, t0, t1, op=1.0):
    """comet along a real 3D arc: a luminous head, a tail that fades behind it, draining into the arrival"""
    k = cv.k
    proj = Proj(cam, cv.W, cv.H)
    p, ok = proj(P3)
    if not ok.all() or op <= 0: return
    s = np.linspace(0, 1, len(P3))
    u = in_out_cubic(lin(t, t0, t1))
    if u <= 0: return
    TAIL = 0.42
    drain = smooth(lin(t, t1, t1+T["drain"]))             # after arrival the tail runs on into Belitung
    a0 = max(0.0, u-TAIL+TAIL*drain); a1 = u
    if a1-a0 < 1e-3: return
    q, su = _partial(p, s, a0, a1)
    z = (np.asarray(P3)-cam.pos)@cam.f
    zq = np.interp(su, s, z)
    wd = np.clip(np.median(z)/zq, 0.6, 1.6)               # nearer = thicker
    x = np.clip((su-(u-TAIL))/TAIL, 0, 1)
    al = (x**1.6)*op*(1-drain)
    for i in range(0, len(q)-1, 6):                       # width follows depth: short chunks
        j = min(i+7, len(q))
        cv.stroke(q[i:j], 2.6*k*float(wd[i:j].mean()), al[i:j], INK, chunks=3)
    cv.glow_poly(q, 5*k, GOLD, 0.28*op*(1-drain))
    if u < 1:
        hs, _ = _partial(p, s, max(0.0, u-0.04), u)
        cv.glow_poly(hs, 6*k, GOLD, 0.40*op)
        cv.glow_dot(q[-1], 6*k, GOLD, 0.55*op)
        cv.disc(q[-1], 2.6*k*float(wd[-1]), 0.95*op, INK)
    else:                                                 # the arrival: a breath of light, not a ping
        g = math.exp(-max(t-t1, 0)/0.6)
        cv.glow_dot(p[-1], 10*k, GOLD, 0.55*g*op)

# ------------------------------------------------------------------ crossing: a wake on the sea
def _route_ll(n=240, bow=450.0):
    ax, ay = xy(*PLACES["teluk_gembira_pier"]); bx, by = xy(*PLACES["seliu_landing"])
    mx, my = (ax+bx)/2, (ay+by)/2; nx, ny = -(by-ay), (bx-ax); L = math.hypot(nx, ny)
    cx, cy = mx+nx/L*bow, my+ny/L*bow
    s = np.linspace(0, 1, n)
    X = (1-s)**2*ax+2*(1-s)*s*cx+s**2*bx; Y = (1-s)**2*ay+2*(1-s)*s*cy+s**2*by
    return X, Y

RX, RY = _route_ll()

def wake(cv, cam, t):
    """a thin luminous strip on the water: bright at the head, widening and dying behind it"""
    k = cv.k
    r0, r1 = T["wake"]; o0, o1 = T["wake_out"]
    u = in_out_sine(lin(t, r0, r1))
    if u <= 0: return
    fade = 1-smooth(lin(t, o0, o1))
    if fade <= 0.003: return
    n = len(RX); s = np.linspace(0, 1, n)
    m = s <= u
    if m.sum() < 2: return
    X, Y = RX[m], RY[m]; ss = s[m]
    # append the exact head
    hx, hy = np.interp(u, s, RX), np.interp(u, s, RY)
    X = np.r_[X, hx]; Y = np.r_[Y, hy]; ss = np.r_[ss, u]
    tx, ty = np.gradient(X), np.gradient(Y); tl = np.hypot(tx, ty)+1e-9
    nx, ny = -ty/tl, tx/tl
    age = u-ss                                            # 0 at the head
    half = 10.0+170.0*np.clip(age/0.6, 0, 1)**0.75        # metres: the wake opens behind the boat
    al = np.exp(-age/0.28)*0.95+0.12*np.exp(-age/1.4)     # bright near the head, a faint long trail
    al = al*fade*np.clip(ss/0.03, 0, 1)
    def P(x, y):
        lo, la = lonlat(x, y); return ecef(np.asarray(la), np.asarray(lo), 1.0)
    proj = Proj(cam, cv.W, cv.H)
    pc, okc = proj(P(X, Y))
    if not okc.all(): return
    Hs, Ws = cv.ink.shape[:2]
    def strip(hw, alpha):
        pl, _ = proj(P(X+nx*hw, Y+ny*hw)); pr, _ = proj(P(X-nx*hw, Y-ny*hw))
        acc = np.zeros((Hs, Ws), np.float32)
        for i in range(len(X)-1):
            a_ = float(0.5*(alpha[i]+alpha[i+1]))
            if a_ < 0.004: continue
            quad = np.array([pl[i], pl[i+1], pr[i+1], pr[i]])*SS
            x0, y0 = np.floor(quad.min(0)).astype(int)-2; x1, y1 = np.ceil(quad.max(0)).astype(int)+2
            x0, y0 = max(x0, 0), max(y0, 0); x1, y1 = min(x1, Ws), min(y1, Hs)
            if x1 <= x0 or y1 <= y0: continue
            sub = np.zeros((y1-y0, x1-x0), np.uint8)
            cv2.fillConvexPoly(sub, np.round((quad-[x0, y0])*16).astype(np.int32), 255, cv2.LINE_AA, shift=4)
            np.maximum(acc[y0:y1, x0:x1], sub.astype(np.float32)/255*a_, out=acc[y0:y1, x0:x1])
        return acc
    soft = cv2.GaussianBlur(strip(half, np.clip(al*1.15, 0, 1)), (0, 0), 1.8*SS*k)   # the opened, foamy water
    core_al = np.exp(-age/0.10)*fade                                      # the bright line dies fast behind
    core = cv2.GaussianBlur(strip(half*0.18+4.0, core_al), (0, 0), 0.7*SS)  # the boat
    cv.over(np.clip(soft+core*0.85, 0, 1), 0, 0, INK)
    cv.glow_poly(pc[-min(len(pc), 50):], 4*k, GOLD, 0.35*fade)
    if u < 1:
        cv.glow_dot(pc[-1], 7*k, GOLD, 0.6*fade)
        cv.disc(pc[-1], 2.0*k, 0.85*fade, INK)

# ------------------------------------------------------------------ Seliu: one light along the real coast
def coast_light(cv, cam, t):
    c0, c1 = T["coast"]
    if not (c0 < t < c1+0.8): return
    k = cv.k
    proj = Proj(cam, cv.W, cv.H)
    p, ok = proj(OUTLINE)
    if ok.mean() < 0.98: return
    s = OUTLINE_S
    u = in_out_cubic(lin(t, c0, c1))
    TAIL = 0.22
    drain = smooth(lin(t, c1, c1+0.7))
    a0 = max(0.0, u-TAIL+TAIL*drain)
    if u-a0 < 1e-3: return
    q, su = _partial(p, s, a0, u)
    x = np.clip((su-(u-TAIL))/TAIL, 0, 1)
    al = x**1.8*(1-drain)
    cv.stroke(q, 2.6*k, al, np.array([1.0, 0.93, 0.80], np.float32), chunks=30)
    for i in range(0, len(q)-1, 8):                       # the glow follows the fading tail
        j = min(i+9, len(q)); cv.glow_poly(q[i:j], 6*k, GOLD, 0.9*float(al[i:j].mean()))
    if u < 1:
        cv.glow_dot(q[-1], 8*k, GOLD, 0.55)
        cv.disc(q[-1], 2.0*k, 0.85, INK)

# ------------------------------------------------------------------ helpers
def ll(key):
    lon, lat = PLACES[key]; return lon, lat

def screen_of(cam, W, H, key, h=0.0):
    lon, lat = PLACES[key]; p, ok = Proj(cam, W, H)(ecef(lat, lon, h)); return p, bool(ok)

# ------------------------------------------------------------------ B placement: chosen on screen, fixed in the world
def ground_at(cam, W, H, sx, sy):
    """ground point under screen pixel (sx, sy): lon, lat, distance (m), |cos| between ray and local vertical"""
    x = (sx/W*2-1)*cam.tanh; y = (1-sy/H*2)*cam.tanv
    d = cam.f+x*cam.r+y*cam.u; d = d/np.linalg.norm(d)
    C = cam.pos; b = d@C; disc = b*b-(C@C-R_E**2)
    if disc <= 0: return None
    tt = -b-math.sqrt(disc); P = C+d*tt
    lat = math.degrees(math.asin(P[2]/np.linalg.norm(P))); lon = math.degrees(math.atan2(P[1], P[0]))
    mu = abs(float(d@(P/np.linalg.norm(P))))
    return lon, lat, tt, mu

def cam_heading(cam, lat, lon):
    e, n, u = enu_basis(lat, lon)
    return math.degrees(math.atan2(float(cam.f@e), float(cam.f@n)))

# name: (t_ref, where, cap_px at 1080 on screen at t_ref). where = ("abs", fx, fy) or ("rel", place|"arc_sin_mid"|"route_mid", dx, dy)
B_SPECS = {
    "16x9": {
        "SINGAPORE":   (6.2, ("rel", "changi", 0.060, 0.010), 26),
        "JAKARTA":     (6.6, ("rel", "cgk", 0.050, -0.030), 26),
        "Direct flights": (6.6, ("rel", "arc_cgk_mid", 0.070, 0.000), 28),
        "BELITUNG":    (12.0, ("abs", 0.50, 0.800), 78),
        "BELITUNG_sub": (12.0, ("abs", 0.50, 0.872), 30),
        "SELIU ISLAND": (24.0, ("abs", 0.42, 0.845), 64),
        "SELIU_sub":   (24.0, ("abs", 0.42, 0.912), 27),
        "TELUK GEMBIRA": (22.0, ("rel", "teluk_gembira_pier", -0.075, 0.080), 30),
        "boat":        (22.5, ("rel", "route_mid", 0.0, -0.050), 32),
    },
    "9x16": {
        "SINGAPORE":   (6.2, ("rel", "changi", 0.0, 0.03), 40),
        "JAKARTA":     (6.6, ("rel", "cgk", 0.0, -0.03), 40),
        "Direct flights": (6.6, ("rel", "arc_sin_mid", 0.14, 0.0), 40),
        "BELITUNG":    (12.0, ("abs", 0.50, 0.70), 80),
        "BELITUNG_sub": (12.0, ("abs", 0.50, 0.76), 32),
        "SELIU ISLAND": (24.0, ("abs", 0.50, 0.74), 70),
        "SELIU_sub":   (24.0, ("abs", 0.50, 0.79), 30),
        "TELUK GEMBIRA": (22.0, ("rel", "teluk_gembira_pier", 0.0, 0.05), 36),
        "boat":        (22.5, ("rel", "route_mid", 0.0, -0.04), 36),
    },
}
_B_CACHE = {}
# every text of one scene lies with the same world orientation (the camera heading at one moment)
SCENE_HEADING_T = {"SINGAPORE": 6.4, "JAKARTA": 6.4, "Direct flights": 6.4, "BELITUNG": 12.0, "BELITUNG_sub": 12.0,
                   "SELIU ISLAND": 23.0, "SELIU_sub": 23.0, "TELUK GEMBIRA": 23.0, "boat": 23.0}

def b_place(name, fmt, W, H):
    """-> anchor (lon, lat), height_m, heading for a B text, solved once from its screen spec"""
    key = (name, fmt, W, H)
    if key in _B_CACHE: return _B_CACHE[key]
    import render_v9 as R
    tref, where, cap = B_SPECS[fmt][name]
    cam = R.cam_at(tref, W, H)
    if where[0] == "abs":
        sx, sy = where[1]*W, where[2]*H
    else:
        ref = where[1]
        if ref == "arc_sin_mid": P = ARC_SIN[len(ARC_SIN)//2]
        elif ref == "arc_cgk_mid": P = ARC_CGK[int(len(ARC_CGK)*0.55)]
        elif ref == "route_mid":
            lo, la = lonlat(RX[len(RX)//2], RY[len(RY)//2]); P = ecef(la, lo)
        else: P = ecef(PLACES[ref][1], PLACES[ref][0])
        p, _ = cam.project(np.asarray(P, np.float64))
        sx, sy = p[0]+where[2]*W, p[1]+where[3]*H
    lon, lat, dist, mu = ground_at(cam, W, H, sx, sy)
    k = min(W, H)/1080
    m_per_px = 2*cam.tanv*dist/H
    # cap ~0.875 of the block ascent. Laid on the ground a word is foreshortened in height but not in width:
    # compensating the height fully makes it twice as wide as a screen title, so only half of it (sqrt)
    height = cap*k*m_per_px/math.sqrt(max(mu, 0.15))/0.875
    th = SCENE_HEADING_T.get(name)
    hd = cam_heading(R.cam_at(th, W, H), lat, lon) if th is not None else cam_heading(cam, lat, lon)
    res = ((lon, lat), height, hd)
    _B_CACHE[key] = res
    return res

def btext(img, cam, fmt, name, s, style, t, t_in, t_out, gesture, rtl=False):
    H, W = img.shape[:2]
    anchor, height, hd = b_place(name, fmt, W, H)
    return world_text(img, cam, s, style, anchor, (0, 0), height, hd, t, t_in, t_out, gesture, rtl=rtl)

# ------------------------------------------------------------------ the graphics
def draw(img, t, cam, fmt="16x9", cam_at=None, style=None):
    style = (style or STYLE).upper()
    H, W = img.shape[:2]
    V = fmt == "9x16"
    img = np.asarray(img, np.float32)
    cv = Canvas(W, H, fmt); k = cv.k

    # ============ REGION: flights ============
    reg = 1.0
    if 3.8 < t < 9.6:
        flight(cv, cam, ARC_SIN, t, *T["arc_sin"], op=reg)
        flight(cv, cam, ARC_CGK, t, *T["arc_cgk"], op=reg)
        if style == "A":
            for key, name, tin, side in (("changi", "SINGAPORE", T["sin_label"], "r"), ("cgk", "JAKARTA", T["cgk_label"], "r")):
                p, ok = screen_of(cam, W, H, key)
                if ok: label_A(cv, name, p, t, tin, T["labels_out"], side=side, opacity=edge_fade(p, W, H, 0.02))
            # the note beside the middle of the Singapore arc, on the open-sea side
            pm, okm = Proj(cam, W, H)(ARC_CGK[int(len(ARC_CGK)*0.55)])
            if okm:
                label_A(cv, "Direct flights", pm, t, T["flights_note"][0], T["flights_note"][1], side="r",
                        style="note", gesture="wipe", dx=22*k, dy=0)
        else:
            img = btext(img, cam, fmt, "SINGAPORE", "SINGAPORE", "place", t, T["sin_label"], T["labels_out"], "fade")
            img = btext(img, cam, fmt, "JAKARTA", "JAKARTA", "place", t, T["cgk_label"], T["labels_out"], "fade")
            img = btext(img, cam, fmt, "Direct flights", "Direct flights", "note", t, *T["flights_note"], "wipe")

    # ============ BELITUNG ============
    tb0, tb1 = T["bel_title"]
    if tb0-0.3 < t < tb1+OUT+0.1:
        if style == "A":
            title_A(cv, t, "BELITUNG", "Bangka Belitung Islands · Indonesia", tb0, T["bel_sub"][0], tb1, T["bel_sub"][1])
        else:
            img = btext(img, cam, fmt, "BELITUNG", "BELITUNG", "title", t, tb0, tb1, "light")
            img = btext(img, cam, fmt, "BELITUNG_sub", "Bangka Belitung Islands · Indonesia", "sub", t, T["bel_sub"][0], T["bel_sub"][1], "wipe")

    # ============ SELIU ============
    coast_light(cv, cam, t)
    if t > T["seliu_title"]-0.3:
        if style == "A":
            title_A(cv, t, "SELIU ISLAND", "Off the south-west coast of Belitung", T["seliu_title"], T["seliu_sub"][0], None, T["seliu_sub"][1])
        else:
            img = btext(img, cam, fmt, "SELIU ISLAND", "SELIU ISLAND", "title", t, T["seliu_title"], None, "light")
            img = btext(img, cam, fmt, "SELIU_sub", "Off the south-west coast of Belitung", "sub", t, T["seliu_sub"][0], T["seliu_sub"][1], "wipe")
    if t > T["tg"][0]-0.1:
        if style == "A":
            p, ok = screen_of(cam, W, H, "teluk_gembira_pier")
            if ok: label_A(cv, "TELUK GEMBIRA", p, t, T["tg"][0], T["tg"][1], side="r", dy=34*k, dx=-4*k)
        else:
            img = btext(img, cam, fmt, "TELUK GEMBIRA", "TELUK GEMBIRA", "place", t, T["tg"][0], T["tg"][1], "fade")
    wake(cv, cam, t)
    if t > T["boat_note"][0]-0.1:
        mx, my = RX[int(0.45*len(RX))], RY[int(0.45*len(RY))]
        lo, la = lonlat(mx, my)
        if style == "A":
            pm, okm = Proj(cam, W, H)(ecef(la, lo))
            if okm: label_A(cv, "15–20 min by boat", pm, t, T["boat_note"][0], T["boat_note"][1], side="c", style="note",
                            gesture="wipe", rtl=True, dy=-44*k)
        else:
            img = btext(img, cam, fmt, "boat", "15–20 min by boat", "note", t, T["boat_note"][0], T["boat_note"][1], "wipe", rtl=True)
    return cv.composite(img)
