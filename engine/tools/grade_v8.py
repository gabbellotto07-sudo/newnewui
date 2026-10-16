"""Seliu v8 grade: grade_cine (v6) with the v8 timing and three corrections asked in the brief.
  1. timing follows the 28 s flight: cold deep orbit -> warming air -> warm luminous arrival
  2. vegetation: no lime. Yellow-greens are pulled toward a deep natural green (hue toward ~120 deg),
     their saturation capped, luminance kept: alive but credible
  3. sand and reef flats: a softer shoulder, so the ring around Seliu is warm, not paper white
Global saturation never above 1. The light on Seliu (+25 % / -30 %) is done in the renderer with the matte.

    grade(img, t, matte=None) -> float32 HxWx3     finish(img, seed) -> uint8 (grain + dither)
"""
import numpy as np, cv2
import grade_cine as G
from grade_cine import finish, LUM            # noqa: F401  (re-exported)
import timeline_v8 as TL

def params(t):
    wo = 1.0-G._ramp(t, 3.0, 9.0)             # orbit / high region
    ws = G._ramp(t, 15.5, 21.0)               # arrival over Seliu
    P = dict(
        wb=G._lerp3([0.97, 0.99, 1.04], [0.995, 1.0, 1.005], [1.03, 1.008, 0.962], wo, ws),
        expo=float(G._lerp3(0.98, 1.0, 1.03, wo, ws)),
        contrast=float(G._lerp3(1.30, 1.30, 1.27, wo, ws)),
        pivot=float(G._lerp3(0.40, 0.46, 0.52, wo, ws)),
        toe=float(G._lerp3(0.004, 0.006, 0.008, wo, ws)),
        sat=float(G._lerp3(0.95, 0.97, 0.97, wo, ws)),
        vib=float(G._lerp3(0.05, 0.07, 0.08, wo, ws)),
        cyan_den=float(G._lerp3(0.07, 0.11, 0.12, wo, ws)),
        split_sh=float(G._lerp3(1.3, 1.1, 0.8, wo, ws)),
        split_hi=float(G._lerp3(0.6, 1.0, 1.4, wo, ws)),
        clarity=float(G._lerp3(0.16, 0.24, 0.24, wo, ws)),
        halation=float(G._lerp3(0.04, 0.05, 0.06, wo, ws)),
        vignette=float(G._lerp3(0.26, 0.20, 0.16, wo, ws)),
        topgrad=float(G._lerp3(0.0, 0.07, 0.08, wo, ws)),
    )
    return P

def _greens(x, amt):
    """lime -> deep natural green: rotate yellow-greens toward green, cap their chroma, keep luminance"""
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    mx = np.maximum(np.maximum(r, g), b); mn = np.minimum(np.minimum(r, g), b); ch = mx-mn
    lime = np.clip((g-b)/0.10, 0, 1)*np.clip((r-b)/0.08, 0, 1)*np.clip((g-r)/0.06, 0, 1)    # yellow-green
    green = np.clip((g-np.maximum(r, b))/0.08, 0, 1)
    l = x@LUM
    y = x.copy()
    y[..., 0] -= amt*0.35*lime*(r-b)                       # less yellow
    y[..., 2] += amt*0.10*lime*(g-b)                       # a breath of blue: natural canopy
    cap = 0.85-0.12*amt*green                               # chroma cap on vegetation
    yl = y@LUM
    k = np.where(green > 0, np.minimum(1.0, cap+(1-cap)*np.clip(1-ch/0.25, 0, 1)), 1.0)
    y = yl[..., None]+(y-yl[..., None])*k[..., None]
    y *= (l/np.maximum(y@LUM, 1e-4))[..., None]           # luminance kept
    return y

def _no_lavender(x):
    """bare soil and clearings seen through blue air drift to lavender: pull r>g<b, low-chroma pixels to warm earth"""
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    w = np.clip((np.minimum(r, b)-g)/0.04, 0, 1)*np.clip(1-(np.maximum(r, b)-np.minimum(r, g))/0.25, 0, 1)
    l = x@LUM
    earth = l[..., None]*np.array([1.10, 0.98, 0.84], np.float32)
    return x*(1-w[..., None]*0.8)+earth*(w[..., None]*0.8)

def _sand(x, amt):
    """bright, low-chroma warm flats (beach, reef flats): roll the top off a little and warm them"""
    l = x@LUM
    w = np.clip((l-0.55)/0.3, 0, 1)
    w = w*w*(3-2*w)*amt
    y = x*(1-0.16*w)[..., None]
    y = y+(w*0.025)[..., None]*np.array([0.9, 0.4, -0.6], np.float32)
    return y

import os
def params_warm(t):
    """variant B: a later-morning warmth on the arrival (more golden air, deeper sea), same structure"""
    P = params(t); ws = G._ramp(t, 15.5, 21.0)
    P["wb"] = np.asarray(P["wb"])*np.array([1+0.035*ws, 1+0.006*ws, 1-0.05*ws], np.float32)
    P["cyan_den"] = P["cyan_den"]+0.05*ws; P["split_hi"] = P["split_hi"]+0.6*ws; P["contrast"] = P["contrast"]+0.03*ws
    return P

def grade(img, t, matte=None):
    G.params = params_warm if os.environ.get("SELIU_LOOK") == "warm" else params
    x = G.grade(img, t)
    ws = G._ramp(t, 12.0, 18.0)
    x = _greens(x, 0.6+0.4*ws)
    x = _no_lavender(x)
    x = _sand(x, ws)
    return np.clip(x, 0, 1).astype(np.float32)
