"""Seliu v9 grade = grade_v8 (look "B caldo", chosen) + the v9 image corrections:
  * sea by depth (15-18 s and the arrival): open, deep water darker and bluer; turquoise kept only where the
    water is really shallow and bright (reef flats, banks), and less saturated overall. Nothing is painted:
    the curve works on what the satellite saw (shallow water is brighter and greener than deep water).
  * Belitung (10-14 s): a little dehaze (the remaining blue-violet lift subtracted) and natural contrast.
    grade(img, t, matte=None) -> float32 HxWx3     finish(img, seed) -> uint8
"""
import numpy as np, cv2
import grade_v8 as G8
from grade_cine import finish, LUM, _ramp      # noqa: F401  (re-exported)

def _water_weight(x):
    """how much a pixel reads as water: blue-dominant or cyan, not vegetation, not sand"""
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    blue = np.clip((b-r)/0.06, 0, 1)
    veg = np.clip((g-b)/0.05, 0, 1)*np.clip((g-r)/0.05, 0, 1)
    return blue*(1-veg)

def _sea(x, amt):
    """deeper water toward ocean blue (hue rotation, not grey), turquoise only on the bright shallows,
    chroma a little lower everywhere on the water"""
    if amt <= 0: return x
    w = _water_weight(x)*amt
    l = x@LUM
    # shallowness: absolute brightness, and brightness relative to the surrounding water (banks, reef flats)
    H, W = l.shape
    sm = cv2.resize(cv2.GaussianBlur(cv2.resize(l, (W//8, H//8), interpolation=cv2.INTER_AREA), (0, 0), 6), (W, H))
    sh = np.clip((l-0.40)/0.22, 0, 1)*0.6+np.clip((l-sm+0.02)/0.08, 0, 1)*0.4
    sh = sh*sh*(3-2*sh)
    deep = (1-sh)*w
    hsv = cv2.cvtColor(np.clip(x, 0, 1).astype(np.float32), cv2.COLOR_RGB2HSV)
    h = hsv[..., 0]
    cyan = np.clip(1-np.abs(h-190)/40, 0, 1)                       # only cyan-ish water hues move
    hsv[..., 0] = h+(204-h)*np.clip(deep*cyan, 0, 1)*0.65          # toward ocean blue
    hsv[..., 1] *= 1-0.10*w-0.06*deep
    hsv[..., 2] *= 1-0.05*deep
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)

def _dehaze(x, amt):
    """remove a uniform blue-violet lift (air light) and restore mid contrast"""
    if amt <= 0: return x
    air = np.array([0.016, 0.020, 0.036], np.float32)*amt
    y = (x-air)/(1-air)
    l = y@LUM
    m = float(np.mean(l))
    y = y+((l-m)*0.06*amt)[..., None]
    return y

def _unvignette(x, amt):
    """take back part of the v8 vignette in the descent (it read as a violet ring around Belitung)"""
    if amt <= 0: return x
    H, W = x.shape[:2]
    v = (np.arange(H, dtype=np.float32)/H*2-1)[:, None]; u = (np.arange(W, dtype=np.float32)/W*2-1)[None, :]
    rr = np.sqrt((u*u+v*v)/2)
    vig = 1-0.20*amt*np.clip((rr-0.38)/0.62, 0, 1)**1.8
    return x/vig[..., None]

def _neutral_black(x, amt):
    """space: the split toning turned the black navy; deep shadows go neutral (the limb keeps its blue)"""
    if amt <= 0: return x
    l = x@LUM
    k = 1-amt*np.clip(1-l/0.035, 0, 1)
    return l[..., None]+(x-l[..., None])*k[..., None]

def grade(img, t, matte=None):
    x = G8.grade(img, t, matte)
    x = _unvignette(x, _ramp(t, 8.0, 10.0)*(1-_ramp(t, 15.0, 17.0)))
    x = _neutral_black(x, 1-_ramp(t, 4.0, 7.0))
    x = _dehaze(x, _ramp(t, 8.0, 10.5)*(1-_ramp(t, 15.0, 17.5)))
    x = _sea(x, _ramp(t, 11.0, 14.0)*(1-0.40*_ramp(t, 19.0, 22.0)))
    return np.clip(x, 0, 1).astype(np.float32)
