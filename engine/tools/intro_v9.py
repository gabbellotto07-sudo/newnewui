"""Seliu v9 — brand opening before the flight (client idea, 16:9).
  0.0-0.5   black space, the same real stars as the orbit (Yale BSC at the orbit camera), fading in
  0.3-1.7   the Compass Rose (official logo, ivory) is born in a dissolve of light
  0.9-2.1   COMPASS ROSE (ivory) rises out of its edge with a fine gold rule; INDONESIA (gold) fades in
  2.6-3.1   the words leave; the ring melts; the rose turns 22.5 deg and contracts into an eight-ray star
  3.35-4.2  the star accelerates toward the lens and passes it: a soft warm flash that dies to black
  then      the flight starts (its own fade from black); the star reappears beyond the limb as a shooting
            star going away into the dark above the Earth, and dies by ~2.3 s
usage: intro_v9.py INTRO_OUT_DIR FINAL_DIR STAR_OUT_DIR    (1920x1080; intro frames i00000.png ...;
       the first frames of FINAL_DIR are copied to STAR_OUT_DIR with the shooting star over them)"""
import sys, os, math, numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import motion_gfx_v9 as M
from motion_gfx import SS, lin, smooth, out_cubic, out_quart, in_out_cubic
import grade_v9 as G

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, FPS = 1920, 1080, 25
DUR = 4.2
IVORY = np.array([0xF5, 0xEF, 0xE6], np.float32)/255
GOLDB = np.array([0xC9, 0xA6, 0x6B], np.float32)/255
WARM = np.array([1.0, 0.93, 0.80], np.float32)

def ease_in(x): x = min(max(x, 0.0), 1.0); return x*x*x

_logo = None
def logo_alpha(px):
    global _logo
    if _logo is None:
        a = cv2.imread(os.path.join(ROOT, "brand", "compass-rose-logo-oro-800.png"), cv2.IMREAD_UNCHANGED)
        _logo = a[..., 3].astype(np.float32)/255
    return cv2.resize(_logo, (px, px), interpolation=cv2.INTER_AREA if px < 800 else cv2.INTER_CUBIC)

def ring_mask(px):
    """the outer circle of the logo (to melt it separately): radius > 0.90 of the half size"""
    yy, xx = np.mgrid[0:px, 0:px].astype(np.float32)
    r = np.hypot(xx-(px-1)/2, yy-(px-1)/2)/(px/2)
    return np.clip((r-0.86)/0.04, 0, 1)

def star_sprite(size, rot, core=1.0):
    """an eight-ray star (the rose's own eight points): long N/E/S/W rays, shorter diagonals, soft core"""
    n = int(size*2.2)|1; c = n//2
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)-c
    r = np.hypot(xx, yy)+1e-3; th = np.arctan2(yy, xx)-math.radians(rot)
    img = core*np.exp(-(r/(0.10*size+0.6))**2)+0.35*core*np.exp(-(r/(0.35*size+1.0))**2)
    for k in range(8):
        a = k*math.pi/4; L = size*(1.0 if k % 2 == 0 else 0.55)
        d = np.abs(np.sin(th-a))*r; along = np.cos(th-a)*r; wr = max(0.9, 0.006*size)
        img += 0.75*np.exp(-(d/wr)**2)*np.clip(1-along/L, 0, 1)**2*(along > 0)
    return np.clip(img, 0, 1.5)

def add_sprite(img, spr, x, y, color, gain=1.0, blur_vec=(0, 0)):
    n = spr.shape[0]; c = n//2
    if abs(blur_vec[0])+abs(blur_vec[1]) > 1.0:                    # motion blur along the screen path
        L = int(min(math.hypot(*blur_vec), 400)); k = np.zeros((2*L+1, 2*L+1), np.float32)
        cv2.line(k, (L-int(blur_vec[0]/2), L-int(blur_vec[1]/2)), (L+int(blur_vec[0]/2), L+int(blur_vec[1]/2)), 1.0, 1, cv2.LINE_AA)
        spr = cv2.filter2D(np.pad(spr, L), -1, k/k.sum()); n = spr.shape[0]; c = n//2
    x0, y0 = int(round(x))-c, int(round(y))-c
    X0, Y0, X1, Y1 = max(x0, 0), max(y0, 0), min(x0+n, W), min(y0+n, H)
    if X1 <= X0 or Y1 <= Y0: return img
    s = spr[Y0-y0:Y1-y0, X0-x0:X1-x0]*gain
    img[Y0:Y1, X0:X1] = 1-(1-img[Y0:Y1, X0:X1])*(1-np.clip(s[..., None]*color, 0, 1))
    return img

def intro_frame(t, stars):
    img = stars*smooth(lin(t, 0.0, 0.6))*(1-smooth(lin(t, 3.4, 3.9)))
    cx, cy = W/2, 452.0
    D = 300                                                            # rose diameter (px)
    # ---- the rose: dissolve of light, slow breathing scale, then turn + contract into the star
    p_in = lin(t, 0.3, 1.7)
    k_c = ease_in(lin(t, 2.75, 3.45))                                  # contraction 0 -> 1
    scale = (0.97+0.03*out_cubic(p_in)+0.012*max(t-1.7, 0))*(1-0.93*k_c)
    rot = 22.5*in_out_cubic(lin(t, 2.6, 3.45))
    if t < 3.5 and p_in > 0:
        px = max(int(D*scale), 8)
        a = logo_alpha(px)
        a = a*(1-ring_mask(px)*smooth(lin(t, 2.55, 3.05)))             # the ring melts first
        Mr = cv2.getRotationMatrix2D(((px-1)/2, (px-1)/2), -rot, 1.0)
        a = cv2.warpAffine(a, Mr, (px, px), flags=cv2.INTER_LINEAR)
        vis = smooth(lin(p_in, 0.25, 1.0))*(1-smooth(lin(k_c, 0.45, 0.85)))
        x0, y0 = int(cx-px/2), int(cy-px/2)
        full = np.zeros((H, W), np.float32); full[y0:y0+px, x0:x0+px] = a
        glow = cv2.GaussianBlur(full, (0, 0), 6+10*(1-p_in))*(0.9*math.sin(math.pi*min(p_in, 1))+0.8*k_c)
        img = img*(1-(full*vis)[..., None])+IVORY*(full*vis)[..., None]
        img = 1-(1-img)*(1-np.clip(glow[..., None]*WARM*0.55, 0, 1))
    # ---- the eight-ray star, born from the contracting rose
    if t >= 2.95:
        b = smooth(lin(t, 2.95, 3.4))
        if t < 3.35:
            img = add_sprite(img, star_sprite(46, rot), cx, cy, IVORY*1.0+0.0, gain=b)
        else:
            # toward the lens: it accelerates from the centre past the lower-right corner, growing continuously
            def path(tt):
                uu = lin(tt, 3.35, 4.05); e = uu*uu*(1.6-0.6*uu)                 # accelerating, no stop
                return cx+(W*0.62)*e, cy+(H*0.55)*e, 46*math.exp(3.6*e), e
            x, y, size, u = path(t)
            x2, y2, _, _ = path(t+0.02)
            pas = 1-smooth(lin(t, 4.0, 4.12))
            if pas > 0:
                img = add_sprite(img, star_sprite(min(size, 1500), rot+50*u), x, y, IVORY, gain=pas, blur_vec=(x2-x, y2-y))
                yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
                rr = np.hypot(xx-x, yy-y)/(0.18*size+30)
                bloom = np.exp(-rr*rr)*0.55+np.exp(-rr)*0.18
                img = 1-(1-img)*(1-np.clip(bloom[..., None]*WARM*(0.3+0.7*u)*pas, 0, 1))
    img = img*(1-smooth(lin(t, 4.05, 4.2)))
    # ---- words: COMPASS ROSE (ivory) rises out of its edge under a gold rule, INDONESIA (gold) fades
    cv = M.Canvas(W, H, "16x9"); k = cv.k
    a1, pad1, asc1, desc1, w1 = M.text_block("COMPASS ROSE", "title", k, 0.62)
    a2, pad2, asc2, desc2, w2 = M.text_block("INDONESIA", "place", k, 0.62)
    out = 1-smooth(lin(t, 2.55, 3.05))
    y1 = 715.0
    p1 = lin(t, 0.9, 2.1)
    if p1 > 0 and out > 0:
        M.put(cv, M.g_mask(a1, p1, pad1, asc1, desc1), cx-w1/SS/2, y1, pad1, asc1, out, color=IVORY)
        r = out_quart(lin(t, 0.75, 1.8)); Lr = 120*k*r
        if Lr > 1:
            xs = np.linspace(cx-Lr, cx+Lr, 31); al = np.clip(1.2-np.abs(np.linspace(-1, 1, 31))**2, 0, 1)*0.85*out
            cv.stroke(np.stack([xs, np.full(31, y1-asc1/SS-30*k)], 1), 1.6*k, al, GOLDB, chunks=12)
        p2 = lin(t, 1.35, 2.25)
        if p2 > 0:
            M.put(cv, M.g_fade(a2, p2), cx-w2/SS/2, y1+64*k, pad2, asc2, out, color=GOLDB)
    return cv.composite(np.clip(img, 0, 1))

def star_stars():
    """the real stars of the first orbit frame, on black"""
    import render_v9 as R
    return R.add_stars(np.zeros((H, W, 3), np.float32)+R.BLACK*2.2, 0.0, W, H)

def shooting_star(img, t):
    """after the pass: the star seen from behind, going away into the dark above the limb, dying"""
    if not (0.10 < t < 2.4): return img
    u = out_cubic(lin(t, 0.10, 2.3))                                   # fast, then slowing with distance
    p0, p1 = np.array([1.03*W, 0.015*H]), np.array([0.40*W, 0.105*H])
    head = p0+(p1-p0)*u
    life = (1-smooth(lin(t, 1.5, 2.35)))*smooth(lin(t, 0.10, 0.3))
    size = 30*(1-u)+5
    # tail: the last 0.35 s of the path, fading toward its end
    us = np.linspace(max(0.0, u-0.28), u, 40)
    pts = p0+(p1-p0)*us[:, None]
    cv = M.Canvas(W, H, "16x9")
    al = np.linspace(0, 1, 40)**2*0.85*life
    cv.stroke(pts, 1.8, al, IVORY, chunks=10)
    cv.glow_poly(pts[-12:], 5, M.GOLD, 0.35*life)
    img = cv.composite(img)
    return add_sprite(img, star_sprite(size, 30+60*u, core=1.0), head[0], head[1], IVORY, gain=life)

def main():
    out_dir, final_dir, star_dir = sys.argv[1:4]
    os.makedirs(out_dir, exist_ok=True); os.makedirs(star_dir, exist_ok=True)
    stars = star_stars()
    n = int(round(DUR*FPS))
    for f in range(n):
        t = f/FPS
        x = intro_frame(t, stars)
        cv2.imwrite(os.path.join(out_dir, f"i{f:05d}.png"), cv2.cvtColor(G.finish(x, seed=90000+f), cv2.COLOR_RGB2BGR))
    for f in range(0, int(2.4*FPS)+1):
        src = os.path.join(final_dir, f"f{f:05d}.png")
        if not os.path.exists(src): continue
        x = cv2.cvtColor(cv2.imread(src), cv2.COLOR_BGR2RGB).astype(np.float32)/255
        x = shooting_star(x, f/FPS)
        cv2.imwrite(os.path.join(star_dir, f"f{f:05d}.png"), cv2.cvtColor((np.clip(x, 0, 1)*255+0.5).astype(np.uint8), cv2.COLOR_RGB2BGR))
    print("intro", n, "frames; shooting star over", int(2.4*FPS)+1, "frames")

if __name__ == "__main__":
    main()
