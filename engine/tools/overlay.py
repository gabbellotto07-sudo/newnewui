"""On-screen writing: few words, each anchored to a real place and drawn in perspective with the camera.
Sized to stay legible on a phone (16:9 watched on a 6" screen, and the 9:16 vertical cut)."""
import os, math, numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
from geo import PLACES
import timeline as TL
FONT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")
INK = (255, 247, 232)          # warm white
SS = 2                          # overlay supersampling
V = TL.FMT == "9x16"
# type scale in px at 1080 on the short side
SZ = dict(city=36, note=38, bel=88, belsub=30, place=34, boat=40, seliu=88, seliusub=30, line=2.8, route=3.4, dot=5.5)
if V: SZ.update(bel=96, seliu=104, city=38, note=40, place=36, boat=44, seliusub=30, belsub=28)
_fc = {}
def font(size, weight=400, italic=False):
    k = (size, weight, italic)
    if k not in _fc:
        f = ImageFont.truetype(os.path.join(FONT, "Jost-Italic-VF.ttf" if italic else "Jost-VF.ttf"), size)
        f.set_variation_by_axes([weight]); _fc[k] = f
    return _fc[k]

def text_width(s, f, track):
    return sum(f.getlength(c) for c in s)+track*f.size*(len(s)-1)

def fit(s, size, weight, track, maxw, italic=False):
    f = font(size, weight, italic)
    while text_width(s, f, track) > maxw and size > 10:
        size = int(size*0.94); f = font(size, weight, italic)
    return f

CLAMP = None   # (W) of the current layer, set in draw(): centred titles never leave the frame
def draw_text(d, xy, s, f, track, alpha, anchor="l"):
    w = text_width(s, f, track); x, y = xy
    if anchor == "c":
        if CLAMP: x = min(max(x, w/2+0.05*CLAMP), CLAMP-w/2-0.05*CLAMP)
        x -= w/2
    elif anchor == "r": x -= w
    for c in s:
        d.text((x, y), c, font=f, fill=INK+(int(255*alpha),), anchor="ls")
        x += f.getlength(c)+track*f.size

def great_circle(a, b, n=240):
    from render import ecef
    A = ecef(a[1], a[0]); B = ecef(b[1], b[0])
    A, B = A/np.linalg.norm(A), B/np.linalg.norm(B)
    om = math.acos(np.clip(A@B, -1, 1)); s = np.linspace(0, 1, n)
    P = (np.sin((1-s)*om)[:, None]*A+np.sin(s*om)[:, None]*B)/math.sin(om)
    return P, s, om

def arc_points(a, b, lift=0.055, n=240):
    from render import R_E
    P, s, om = great_circle(a, b, n)
    h = lift*om*R_E*np.sin(np.pi*s)
    return P*(R_E+h)[:, None]

def ground(lon, lat, h=0.0):
    from render import ecef
    return ecef(lat, lon, h)

def edge_fade(p, W, H, m=0.05):
    x, y = p
    fx = min(x/W, 1-x/W)/m; fy = min(y/H, 1-y/H)/m
    return float(np.clip(min(fx, fy), 0, 1))

def draw(img, t, cam):
    H, W = img.shape[:2]; S = SS
    global CLAMP; CLAMP = W*S
    layer = Image.new("RGBA", (W*S, H*S), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
    sc = min(W, H)/1080.0*S
    def P2(Pw):
        p, z = cam.project(np.asarray(Pw)); return p*S, z
    def line(pts, width, alpha):
        if len(pts) < 2 or alpha <= 0.01: return
        d.line([tuple(map(float, q)) for q in pts], fill=INK+(int(255*alpha),), width=max(1, int(round(width*sc))), joint="curve")
    def dot(p, r, alpha):
        if alpha <= 0.01: return
        r *= sc; d.ellipse([p[0]-r, p[1]-r, p[0]+r, p[1]+r], fill=INK+(int(255*alpha),))
    ramp = TL.ramp
    vis = lambda p: edge_fade(p/S, W, H)

    # ---- region: flights ----------------------------------------------------------
    a_reg = ramp(t, 2.6, 3.8)*(1-ramp(t, 8.9, 9.6))
    tjq = PLACES["tjq"]
    for key, name, t0, t1 in (("changi", "SINGAPORE", 4.4, 7.2), ("cgk", "JAKARTA", 5.0, 7.8)):
        src = PLACES[key]
        p, z = P2(arc_points(src, tjq)); prog = ramp(t, t0, t1); k = int(prog*(len(p)-1))
        if a_reg > 0 and prog > 0 and (z > 0).all():
            line(p[:k+1], SZ["line"], 0.88*a_reg)
            if prog < 1: dot(p[k], SZ["dot"]*0.9, a_reg)
        ps, zs = P2(ground(*src)); al = a_reg*vis(ps)
        if zs > 0 and al > 0:
            dot(ps, SZ["dot"], al)
            draw_text(d, (ps[0]+16*sc, ps[1]+10*sc), name, font(int(SZ["city"]*sc), 500), 0.2, al)
    pt, zt = P2(ground(*tjq))
    if zt > 0: dot(pt, SZ["dot"], a_reg*ramp(t, 7.0, 7.6))
    al = ramp(t, 7.4, 8.2)*(1-ramp(t, 10.0, 10.6))
    pb, zb = P2(ground(*PLACES["belitung_centre"]))
    if al > 0 and zb > 0:
        draw_text(d, (pb[0]+30*sc, pb[1]+10*sc), "BELITUNG", font(int(SZ["city"]*sc), 500), 0.2, al*vis(pb))
    al = a_reg*ramp(t, 5.4, 6.6)
    if al > 0:
        p, z = P2(arc_points(PLACES["changi"], tjq)); q = p[int(0.5*len(p))]
        draw_text(d, (q[0]+22*sc, q[1]), "Direct flights", font(int(SZ["note"]*sc), 400, italic=True), 0.03, al*vis(q))

    # ---- Belitung -----------------------------------------------------------------
    al = ramp(t, 10.6, 11.8)*(1-ramp(t, 12.9, 13.7))
    if al > 0:
        p, z = P2(ground(*PLACES["belitung_centre"]))
        if z > 0:
            rise = (1-ramp(t, 10.6, 12.4))*10*sc
            f = fit("BELITUNG", int(SZ["bel"]*sc), 400, 0.42, W*S*0.8)
            draw_text(d, (p[0], p[1]+rise), "BELITUNG", f, 0.42+0.03*ramp(t, 10.6, 14.8), al, "c")
            fs = fit("BANGKA BELITUNG ISLANDS  ·  INDONESIA", int(SZ["belsub"]*sc), 500, 0.22, W*S*0.86)
            draw_text(d, (p[0], p[1]+f.size*0.62+rise), "BANGKA BELITUNG ISLANDS  ·  INDONESIA", fs, 0.22, al*0.92, "c")

    # ---- Seliu --------------------------------------------------------------------
    pier = PLACES["teluk_gembira_pier"]; landp = PLACES["seliu_landing"]
    al = ramp(t, 18.6, 19.6)
    p, z = P2(ground(*pier))
    if al > 0 and z > 0:
        dot(p, SZ["dot"], al)
        if V: draw_text(d, (p[0], p[1]+44*sc), "TELUK GEMBIRA", font(int(SZ["place"]*sc), 500), 0.2, al, "c")
        else: draw_text(d, (p[0]+16*sc, p[1]+10*sc), "TELUK GEMBIRA", font(int(SZ["place"]*sc), 500), 0.2, al)
    prog = ramp(t, 19.8, 22.6)
    if prog > 0:
        from render import aeqd
        from geo import lonlat
        ax, ay = aeqd(pier[1], pier[0]); bx, by = aeqd(landp[1], landp[0])
        mx, my = (ax+bx)/2, (ay+by)/2; nx, ny = -(by-ay), (bx-ax); L = math.hypot(nx, ny)
        cx, cy = mx+nx/L*450, my+ny/L*450                   # gentle bow to the north, over open water
        s_ = np.linspace(0, 1, 200)
        X = (1-s_)**2*ax+2*(1-s_)*s_*cx+s_**2*bx; Y = (1-s_)**2*ay+2*(1-s_)*s_*cy+s_**2*by
        lo, la = lonlat(X, Y)
        p, z = P2(np.stack([ground(o, a, 6.0) for o, a in zip(lo, la)]))
        k = int(prog*(len(p)-1))
        line(p[:k+1], SZ["route"], 0.95)
        if prog < 1: dot(p[k], SZ["dot"]*0.95, 1.0)
        al2 = ramp(t, 21.4, 22.6)
        if al2 > 0:
            q = p[len(p)//2]
            if V: draw_text(d, (q[0]+26*sc, q[1]+12*sc), "15–20 min by boat", font(int(SZ["boat"]*sc), 400, italic=True), 0.02, al2)
            else: draw_text(d, (q[0], q[1]-24*sc), "15–20 min by boat", font(int(SZ["boat"]*sc), 400, italic=True), 0.02, al2, "c")
        dot(p[-1], SZ["dot"]*0.8, ramp(t, 22.4, 23.0)*0.95)
    al = ramp(t, 17.4, 18.8)
    if al > 0:
        anchor = PLACES["seliu_label"]
        p, z = P2(ground(*anchor))
        if z > 0:
            f = fit("SELIU ISLAND", int(SZ["seliu"]*sc), 400, 0.34, W*S*0.86)
            fs = fit("OFF THE SOUTH-WEST COAST OF BELITUNG", int(SZ["seliusub"]*sc), 500, 0.2, W*S*0.86)
            # the name sits in the haze above the island, a hairline down to it
            x0, y0 = (p[0], p[1]-250*sc) if not V else (W*S/2, p[1]-230*sc)
            tw = text_width("SELIU ISLAND", f, 0.34); x0 = min(max(x0, tw/2+0.05*W*S), W*S-tw/2-0.05*W*S)
            d.line([(p[0], p[1]-70*sc), (p[0], y0+fs.size*2.6)], fill=INK+(int(180*al),), width=max(1, int(1.2*sc)))
            draw_text(d, (x0, y0), "SELIU ISLAND", f, 0.34, al, "c")
            draw_text(d, (x0, y0+fs.size*1.9), "OFF THE SOUTH-WEST COAST OF BELITUNG", fs, 0.2, al*0.92, "c")

    # composite: soft shadow for legibility, then ink
    a = np.asarray(layer).astype(np.float32)/255.0
    a = cv2.resize(a, (W, H), interpolation=cv2.INTER_AREA)
    alpha = a[..., 3:4]
    sh = cv2.GaussianBlur(alpha[..., 0], (0, 0), 4.0*min(W, H)/1080)[..., None]
    img = img*(1-0.42*np.clip(sh*1.6, 0, 1))
    col = a[..., :3]/np.maximum(alpha, 1e-4)
    return img*(1-alpha)+col*alpha
