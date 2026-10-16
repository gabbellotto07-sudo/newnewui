"""Seliu v8 — the whole opening on one table: camera path, light, fades. Times in seconds, 25 fps.

One physical camera: a satellite that becomes an aircraft that becomes a helicopter.
Each key: t, target lat, target lon, slant range (km), heading (deg, 0 = looking north),
tilt (deg from nadir), roll (deg, + = image turns clockwise, the bank of a right turn).
Between keys: monotone cubic (PCHIP) on lat/lon/heading/tilt/roll and on log(range), so speed
changes are smooth and there is never an overshoot. Change the path here and nowhere else.
SELIU_FMT=9x16 selects the vertical flight (same until Belitung, then it turns to look west).
"""
import os, numpy as np
from scipy.interpolate import PchipInterpolator

FMT = os.environ.get("SELIU_FMT", "16x9")
FPS = 25
DURATION = 28.0
VFOV = 36.0 if FMT == "16x9" else 58.0

#       t      lat       lon      range_km  head   tilt   roll
KEYS = [
    (0.0,  -0.95,   105.05,   6600,    -7.0,  64.0,   0.0),   # orbit: the limb across the top, Sundaland below
    (3.6,  -1.95,   105.75,   3700,    -4.0,  54.0,   0.4),
    (6.8,  -2.55,   106.45,   1850,     3.0,  45.0,   1.4),   # flights: Singapore far, Jakarta near, Belitung right
    (9.9,  -2.84,   107.62,    470,    12.0,  38.0,   1.2),   # bending toward Belitung
    (12.6, -2.93,   107.80,    225,    18.0,  40.0,   0.0),   # BELITUNG, the camera almost still
    (15.3, -3.13,   107.50,     38,    32.0,  56.0,  -2.0),   # dive over the real cumulus field, south-west of Seliu
    (17.8, -3.214,  107.528,    13.5,  14.0,  62.0,  -3.0),   # out of the clouds: Seliu ahead, banking into the turn
    (20.8, -3.213,  107.548,     9.4,  -7.0,  63.5,  -1.4),
    (24.0, -3.214,  107.552,     8.6, -13.5,  63.8,  -0.5),
    (28.0, -3.215,  107.553,     8.2, -17.0,  63.6,   0.0),   # the hold: a slow helicopter drift, never still
]
if FMT == "9x16":
    KEYS = KEYS[:5]+[
        (15.3, -3.12,   107.64,     40,   -18.0,  55.0,   1.5),
        (18.0, -3.204,  107.578,    14.0,  -62.0,  60.0,   2.5),
        (21.0, -3.206,  107.563,    10.2,  -84.0,  62.5,   1.0),
        (24.0, -3.207,  107.559,     9.4,  -89.0,  63.0,   0.3),
        (28.0, -3.207,  107.556,     9.0,  -91.5,  63.0,   0.0),
    ]
_k = np.array(KEYS, float)
_f = {i: PchipInterpolator(_k[:, 0], _k[:, i]) for i in (1, 2, 4, 5, 6)}
_r = PchipInterpolator(_k[:, 0], np.log(_k[:, 3]))

def ramp(t, a, b):
    x = np.clip((t-a)/(b-a), 0, 1); return float(x*x*(3-2*x))

def camera(t):
    """-> lat, lon, range_m, heading, tilt, roll"""
    t = float(np.clip(t, 0, DURATION))
    lat, lon, hd, tl, rl = (float(_f[i](t)) for i in (1, 2, 4, 5, 6))
    # the final approach breathes like a helicopter hold: tiny, incommensurate, never a loop
    w = ramp(t, 17.0, 21.0)
    hd += w*(0.30*np.sin(2*np.pi*0.067*t+0.4)+0.10*np.sin(2*np.pi*0.173*t))
    tl += w*(0.20*np.sin(2*np.pi*0.089*t+1.3)+0.07*np.sin(2*np.pi*0.21*t+0.7))
    rl += w*(0.25*np.sin(2*np.pi*0.11*t+2.1))
    return lat, lon, float(np.exp(_r(t)))*1000.0, hd, tl, rl

def fade(t):            # from black in 0.6 s; the camera is already moving
    return ramp(t, 0.02, 0.6)

def glow(t):            # Seliu catches the light as the camera leaves the clouds
    return ramp(t, 16.8, 20.8)

def warmth(t):          # 0 = cold orbit, 1 = warm arrival: drives grade and atmosphere colour
    return ramp(t, 4.0, 12.0)*0.45+ramp(t, 13.0, 20.0)*0.55
