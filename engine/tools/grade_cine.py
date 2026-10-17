"""Seliu v6 -- cinematic colour grade applied on top of the RAW plates (frames/raw_*).

The RAW plates already carry the base look (filmic tone map, light on Seliu, warm bloom on whites).
This module adds the "film" layer requested by the client: deeper, more immersive, still satellite-true.

    grade(img, t)      float32 HxWx3 in 0..1 (display-referred RGB) -> float32 HxWx3 in 0..1
    finish(img, seed)  film grain + triangular dither -> uint8 HxWx3 RGB (call LAST, after graphics)

Grade order (display space unless noted):
  1. white balance + exposure in (approx.) linear light, time-varying (cool orbit -> warm Seliu)
  2. filmic contrast around a mid pivot, applied mostly on luminance (hue-preserving), soft toe
  3. highlight roll-off (shoulder): whites never clip hard, peak ~0.975
  4. selective colour: turquoise shallows a touch denser/less saturated, greens slightly deeper,
     gentle vibrance for low-chroma areas; global saturation capped (never oversaturated)
  5. split toning: cool teal shadows, warm highlights (very small amounts)
  6. large-radius local contrast ("dimension"), computed at 1/8 resolution, very low amount
  7. halation: red-orange film halation around the brightest highlights (reef flats, cloud tops)
  8. vignette: elliptical, soft, stronger in orbit, lighter on the final hold
"""
import numpy as np, cv2

LUM = np.array([0.2126, 0.7152, 0.0722], np.float32)


def _ramp(t, a, b):
    x = min(max((t-a)/(b-a), 0.0), 1.0)
    return x*x*(3-2*x)


def _lerp3(a, b, c, w_orbit, w_seliu):
    """blend a parameter between orbit / descent / Seliu states"""
    a, b, c = (np.asarray(v, np.float32) for v in (a, b, c))
    mid = a*w_orbit+b*(1-w_orbit)
    return mid*(1-w_seliu)+c*w_seliu


def params(t):
    """time-varying grade parameters (seconds on the 25 s 16:9 / 9:16 timeline)"""
    wo = 1.0-_ramp(t, 3.5, 9.0)            # orbit / high region: cooler, deeper, more contrast
    ws = _ramp(t, 14.5, 20.0)              # arrival over Seliu: warmer, more luminous, softer contrast
    P = dict(
        wb=_lerp3([0.975, 0.995, 1.035], [0.995, 1.0, 1.005], [1.035, 1.01, 0.958], wo, ws),
        expo=float(_lerp3(0.97, 1.0, 1.04, wo, ws)),            # linear gain
        contrast=float(_lerp3(1.26, 1.24, 1.22, wo, ws)),
        pivot=float(_lerp3(0.40, 0.46, 0.54, wo, ws)),           # near the real mids of each act
        toe=float(_lerp3(0.008, 0.014, 0.018, wo, ws)),          # black lift (cool), keeps blacks filmic
        sat=float(_lerp3(0.96, 0.98, 0.99, wo, ws)),
        vib=float(_lerp3(0.05, 0.08, 0.10, wo, ws)),
        cyan_den=float(_lerp3(0.07, 0.12, 0.13, wo, ws)),          # turquoise density
        split_sh=float(_lerp3(1.3, 1.1, 0.9, wo, ws)),             # shadow teal amount
        split_hi=float(_lerp3(0.6, 1.0, 1.6, wo, ws)),             # highlight warmth amount
        clarity=float(_lerp3(0.14, 0.20, 0.20, wo, ws)),
        halation=float(_lerp3(0.05, 0.06, 0.08, wo, ws)),
        vignette=float(_lerp3(0.26, 0.20, 0.15, wo, ws)),
        topgrad=float(_lerp3(0.0, 0.08, 0.10, wo, ws)),            # soft cool ND grad toward the far sea
    )
    return P


def _scurve(y, c, p):
    """contrast around pivot p, C1-continuous (slope c at the pivot), monotone"""
    lo = p*np.power(np.clip(y/p, 0, 1), c)
    hi = 1-(1-p)*np.power(np.clip((1-y)/(1-p), 0, 1), c)
    return np.where(y < p, lo, hi)


def _tone_lut(P, n=2048):
    x = np.linspace(0, 1, n, dtype=np.float32)
    y = _scurve(x, P["contrast"], P["pivot"])
    # keep the deepest shadows open: blend back to identity near black (soft toe, no crushing)
    w = np.clip(x/0.12, 0, 1); w = w*w*(3-2*w)
    y = y*w+x*(1-w)*0.92
    # shoulder: soft highlight roll-off above the knee
    k = 0.80
    over = np.clip(y-k, 0, None)
    y = np.where(y > k, k+(1-k)*0.975*np.tanh(over/((1-k)*0.975)), y)
    y = P["toe"]+y*(1-P["toe"])
    return x, y.astype(np.float32)


def grade(img, t):
    img = np.asarray(img, np.float32)
    H, W = img.shape[:2]
    P = params(t)
    # 1. white balance / exposure in linear light -- per-channel 12-bit LUTs (fast, exact enough)
    N = 4096
    v = np.linspace(0, 1, N, dtype=np.float32)
    idx = np.clip(img*(N-1)+0.5, 0, N-1).astype(np.int32)
    x = np.empty_like(img)
    for c in range(3):
        lut = np.power(np.power(v, 2.2)*float(P["wb"][c]*P["expo"]), 1/2.2).astype(np.float32)
        x[..., c] = lut[idx[..., c]]
    # 2-3. tone curve on luminance (hue preserving) blended with a little per-channel curve
    xs, ys = _tone_lut(P, N)
    l = x@LUM
    li = np.clip(l*(N-1)+0.5, 0, N-1).astype(np.int32)
    ratio = (ys[li]/np.maximum(l, 1e-4))[..., None]
    per = ys[np.clip(x*(N-1)+0.5, 0, N-1).astype(np.int32)]
    x = 0.75*np.minimum(x*ratio, 1.2)+0.25*per
    # soft clip of anything the ratio pushed above white, toward the luminance (no hue skew)
    l = (x@LUM)[..., None]
    mx = np.maximum(np.maximum(x[..., 0], x[..., 1]), x[..., 2])[..., None]
    k = np.clip((mx-0.97)/0.25, 0, 1)
    x = x*(1-k)+np.minimum(l, 0.98)*k
    # 4. selective colour
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    mx = np.maximum(np.maximum(r, g), b); mn = np.minimum(np.minimum(r, g), b); chroma = mx-mn
    l = x@LUM
    # turquoise / cyan shallows: denser and slightly less saturated (richer, less "pool")
    wc = np.clip((np.minimum(g, b)-r)/0.25, 0, 1)*np.clip(1-np.abs(g-b)/0.22, 0, 1)
    dens = 1-P["cyan_den"]*wc
    # vibrance: lift low-chroma colours a touch, never the already-saturated ones
    sat = P["sat"]*(1+P["vib"]*np.clip(1-chroma/0.35, 0, 1))*(1-0.5*P["cyan_den"]*wc)
    x = l[..., None]+(x-l[..., None])*sat[..., None]
    x = x*dens[..., None]
    # greens: a little deeper / more olive (forest canopy reads richer)
    wg = np.clip((g-np.maximum(r, b))/0.12, 0, 1)
    x[..., 1] -= 0.012*wg*l
    x[..., 0] += 0.004*wg*l
    # 5. split toning
    l = np.clip(x@LUM, 0, 1)[..., None]
    sh = (1-l)*(1-l); hi = l*l*np.sqrt(l)        # ~(1-l)^2, l^2.5
    x = x+P["split_sh"]*sh*np.array([-0.010, 0.002, 0.014], np.float32)
    x = x+P["split_hi"]*hi*np.array([0.016, 0.005, -0.016], np.float32)
    # 6. large-radius local contrast on luminance (computed small, it is a low frequency)
    l = (x@LUM).astype(np.float32)
    sw, sh_ = max(W//8, 8), max(H//8, 8)
    small = cv2.resize(l, (sw, sh_), interpolation=cv2.INTER_AREA)
    blur = cv2.GaussianBlur(small, (0, 0), 6.0)
    blur = cv2.resize(blur, (W, H), interpolation=cv2.INTER_LINEAR)
    detail = np.clip(l-blur, -0.12, 0.12)
    prot = np.clip(1-np.abs(l-0.5)*1.6, 0.2, 1)            # protect deep blacks and bright whites
    x = x+(P["clarity"]*detail*prot)[..., None]
    # 7. halation: film red layer bleeding around the brightest highlights
    l = np.clip(x@LUM, 0, 1)
    hl = np.clip((l-0.72)/0.28, 0, 1); hl = hl*np.sqrt(hl)
    q = cv2.resize(hl, (max(W//4, 4), max(H//4, 4)), interpolation=cv2.INTER_AREA)
    s = min(W, H)/1080
    h1 = cv2.GaussianBlur(q, (0, 0), 2.0*s); h2 = cv2.GaussianBlur(q, (0, 0), 7.0*s)
    hal = cv2.resize(0.6*h1+0.4*h2, (W, H), interpolation=cv2.INTER_LINEAR)
    hal = np.clip(hal-0.5*hl, 0, 1)                         # mostly around, not on, the highlight
    x = x+(P["halation"]*hal)[..., None]*np.array([1.0, 0.42, 0.22], np.float32)
    # 8. vignette (elliptical, aspect-aware)
    # normalised elliptical radius: 0 at centre, ~0.71 mid-edges, 1 in the corners (any aspect)
    v = (np.arange(H, dtype=np.float32)/H*2-1)[:, None]
    u = (np.arange(W, dtype=np.float32)/W*2-1)[None, :]
    rr = np.sqrt((u*u+v*v)/2)
    vig = 1-P["vignette"]*np.clip((rr-0.38)/0.62, 0, 1)**1.8
    x = x*vig[..., None]
    if P["topgrad"] > 0:
        gy = np.clip(1-(np.arange(H, dtype=np.float32)/H)/0.5, 0, 1); gy = gy*gy*(3-2*gy)
        gr = (1-P["topgrad"]*gy)[:, None, None]*np.array([0.985, 0.995, 1.0], np.float32)**gy[:, None, None]
        x = x*gr
    return np.clip(x, 0, 1).astype(np.float32)


def finish(img, seed, amount=1.0):
    """film grain (luma-weighted, slightly chromatic, ~1.3 px grain) + TPDF dither -> uint8 RGB.
    Grain is strongest in the mids, gentle in deep shadows and highlights (like a 35 mm scan, very fine)."""
    img = np.asarray(img, np.float32)
    H, W = img.shape[:2]
    rng = np.random.default_rng(int(seed))
    s = min(W, H)/1080
    gl = rng.standard_normal((H, W), dtype=np.float32)
    gl = cv2.GaussianBlur(gl, (0, 0), 0.65*s)
    gl /= max(float(gl.std()), 1e-6)
    gc = rng.standard_normal((H//2, W//2, 3), dtype=np.float32)
    gc = cv2.resize(cv2.GaussianBlur(gc, (0, 0), 0.6), (W, H), interpolation=cv2.INTER_LINEAR)
    gc /= max(float(gc.std()), 1e-6)
    l = np.clip(img@LUM, 0, 1)
    resp = 0.35+0.65*np.clip(4*l*(1-l), 0, 1)**0.8          # mid-weighted response
    amp = (0.0115*amount*resp)[..., None]
    x = img+amp*(0.8*gl[..., None]+0.2*gc)
    # triangular-PDF dither at 1 LSB, then quantize
    d = (rng.random((H, W, 3), dtype=np.float32)-rng.random((H, W, 3), dtype=np.float32))/255.0
    return np.clip((x+d)*255.0+0.5, 0, 255).astype(np.uint8)
