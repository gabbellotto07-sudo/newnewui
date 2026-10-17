"""Timing of the whole opening: camera path, light, fades. All times in seconds."""
import os, numpy as np
FMT = os.environ.get("SELIU_FMT", "16x9")
from scipy.interpolate import PchipInterpolator
DURATION = 25.0
VFOV = 34.0 if FMT == "16x9" else 58.0
# t, lat, lon, slant range (km), heading (deg, 0=north up), tilt (deg from nadir)
KEYS = [
    (0.0,  -0.60, 105.60, 5600, -8.0, 62.0),
    (3.2,  -1.90, 106.05, 3300, -6.0, 22.0),
    (6.6,  -2.42, 106.20, 2150, -3.5,  5.0),
    (10.1, -2.78, 107.40,  480, -1.0,  4.0),
    (13.1, -2.98, 107.68,  130,  1.0,  8.0),
    (15.6, -3.15, 107.585,  46, -4.0, 22.0),
    (18.6, -3.200, 107.562,  25.0, -9.0, 40.0),
    (22.1, -3.217, 107.548,  18.0, -12.5, 50.0),
    (25.0, -3.221, 107.543,  16.6, -14.0, 52.0),
]
if FMT == "9x16":
    # vertical: same flight, then a slow turn to look west from Teluk Gembira toward Seliu
    KEYS = KEYS[:5]+[
        (15.6, -3.16, 107.592,  52, -30.0, 22.0),
        (18.6, -3.203, 107.572,  27, -68.0, 40.0),
        (22.1, -3.206, 107.561,  17.5, -85.0, 50.0),
        (25.0, -3.207, 107.557,  15.8, -90.0, 53.0),
    ]
_k = np.array(KEYS, float)
_f = [PchipInterpolator(_k[:, 0], _k[:, i]) for i in (1, 2, 4, 5)]
_r = PchipInterpolator(_k[:, 0], np.log(_k[:, 3]))
def camera(t):
    t = float(np.clip(t, 0, DURATION))
    lat, lon, hd, tl = (float(f(t)) for f in _f)
    # the final approach breathes like a helicopter hold, never a locked-off map
    w = ramp(t, 15.0, 19.0)
    hd += w*(0.35*np.sin(2*np.pi*0.071*t+0.4)+0.12*np.sin(2*np.pi*0.19*t))
    tl += w*(0.25*np.sin(2*np.pi*0.093*t+1.3)+0.08*np.sin(2*np.pi*0.23*t+0.7))
    return lat, lon, float(np.exp(_r(t)))*1000.0, hd, tl
def blur_samples(t):
    """shutter offsets (s) for motion blur: only while the dive is fast"""
    k = ramp(t, 6.0, 7.5)*(1-ramp(t, 15.5, 17.0))
    return [0.0] if k < 0.05 else [-0.009*k, 0.009*k]
def ramp(t, a, b):
    x = np.clip((t-a)/(b-a), 0, 1); return float(x*x*(3-2*x))
def fade(t):            # picture fades up from black after the first sound
    return ramp(t, 0.05, 1.0)
def glow(t):            # Seliu catches the light
    return ramp(t, 16.0, 20.0)

# ---- raw library: single shots with eased, slow moves (SELIU_SHOT=<name> from tools/shots.json)
SHOT = os.environ.get("SELIU_SHOT")
if SHOT:
    import json as _json
    _S = _json.load(open(os.path.join(os.path.dirname(__file__), "shots.json")))[SHOT]
    DURATION = float(_S["dur"])
    def camera(t):
        u = float(np.clip(t/DURATION, 0, 1)); e = u*u*u*(u*(u*6-15)+10)      # smootherstep
        a, b = np.array(_S["a"], float), np.array(_S["b"], float)
        p = a+(b-a)*e
        r = float(np.exp(np.log(a[2])+(np.log(b[2])-np.log(a[2]))*e))*1000.0
        return float(p[0]), float(p[1]), r, float(p[3]), float(p[4])
    def blur_samples(t): return [0.0]
    def fade(t): return 1.0
    _G = float(os.environ.get("SELIU_GLOW", "0"))
    def glow(t): return _G
