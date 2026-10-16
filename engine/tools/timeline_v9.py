"""Seliu v9 — same flight as v8 from 6.8 s; the orbit now travels and turns from the first frame and
the descent starts by ~2 s. (v8 header follows)
Seliu v8 — the whole opening on one table: camera path, light, fades. Times in seconds, 25 fps.

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
    (0.0,   2.60,   103.20,   7600,   -27.0,  63.0,  -1.6),   # orbit: travelling south-east, turning right
    (3.6,  -1.70,   105.55,   3800,    -6.0,  54.0,   0.6),
    (6.8,  -2.55,   106.45,   1850,     3.0,  45.0,   1.4),   # flights: Singapore far, Jakarta near, Belitung right
    (9.9,  -2.84,   107.62,    470,    12.0,  38.0,   1.2),   # bending toward Belitung
    (11.6, -2.90,   107.76,    290,    16.0,  39.0,   0.4),   # BELITUNG: the camera settles...
    (12.4, -2.945,  107.805,   240,    18.5,  40.8,   0.1),   # v9: the hold ends earlier, so the dive gathers speed over ~1.6 s   # ...almost still under the title
    (15.5, -3.13,   107.50,     36,    32.0,  56.0,  -2.0),   # dive over the real cumulus field, south-west of Seliu
    (17.8, -3.221,  107.524,    13.5,  14.0,  62.0,  -3.0),   # out of the clouds: Seliu ahead, banking into the turn
    (20.8, -3.228,  107.537,    12.6,  -7.0,  60.0,  -1.2),   # v9: target ~1 km further south than v8, so the
    (24.0, -3.230,  107.538,    11.5, -12.0,  60.0,  -0.4),   # island sits higher and the sea below it is free
    (28.0, -3.230,  107.538,    11.0, -15.0,  60.5,   0.0),   # the hold: a slow helicopter drift, never still
    (31.0, -3.230,  107.538,    10.6, -17.4,  60.8,   0.2),   # beyond the cut: keeps the drift alive on the last frame
]
if FMT == "9x16":
    # v9: the taller frame saw Australia's red interior at the bottom of the orbit: look a little higher
    KEYS = [(0.0, 5.00, 103.50, 7200, 18.0, 62.0, -1.2), (3.6, -1.70, 105.55, 3800, -6.0, 58.0, 0.6)]+KEYS[2:6]+[
        (15.3, -3.12,   107.64,     40,   -18.0,  55.0,   1.5),
        (18.0, -3.204,  107.575,    14.0,  -70.0,  59.0,   2.5),
        (21.0, -3.208,  107.560,    11.8, -98.0,  58.5,   1.0),
        (24.0, -3.210,  107.554,    10.7, -106.0, 58.0,   0.3),
        (28.0, -3.210,  107.553,    10.4, -108.0, 58.2,   0.0),
        (31.0, -3.210,  107.552,    10.1, -109.5, 58.4,   0.2),
    ]
_k = np.array(KEYS, float)
_f = {i: PchipInterpolator(_k[:, 0], _k[:, i]) for i in (1, 2, 4, 5, 6)}
_r = PchipInterpolator(_k[:, 0], np.log(_k[:, 3]))

def ramp(t, a, b):
    x = np.clip((t-a)/(b-a), 0, 1); return float(x*x*(3-2*x))

def camera(t):
    """-> lat, lon, range_m, heading, tilt, roll"""
    t = float(np.clip(t, 0, DURATION+0.5))
    lat, lon, hd, tl, rl = (float(_f[i](t)) for i in (1, 2, 4, 5, 6))
    # the final approach breathes like a helicopter hold: tiny, incommensurate, never a loop
    w = ramp(t, 17.0, 21.0)
    hd += w*(0.30*np.sin(2*np.pi*0.067*t+0.4)+0.10*np.sin(2*np.pi*0.173*t))
    tl += w*(0.20*np.sin(2*np.pi*0.089*t+1.3)+0.07*np.sin(2*np.pi*0.21*t+0.7))
    rl += w*(0.25*np.sin(2*np.pi*0.11*t+2.1))
    # v9: the aircraft before it: a slow, barely felt float in the descent (never a shake)
    w2 = ramp(t, 1.0, 4.0)*(1-ramp(t, 15.5, 17.5))
    hd += w2*(0.16*np.sin(2*np.pi*0.071*t+0.9)+0.06*np.sin(2*np.pi*0.19*t+2.0))
    tl += w2*(0.12*np.sin(2*np.pi*0.093*t+0.2))
    rl += w2*(0.35*np.sin(2*np.pi*0.083*t+1.7)+0.10*np.sin(2*np.pi*0.23*t))
    return lat, lon, float(np.exp(_r(t)))*1000.0, hd, tl, rl

def fade(t):            # from black in 0.6 s; the camera is already moving
    return ramp(t, 0.02, 0.6)

def glow(t):            # Seliu catches the light as the camera leaves the clouds
    return ramp(t, 16.8, 20.8)

def warmth(t):          # 0 = cold orbit, 1 = warm arrival: drives grade and atmosphere colour
    return ramp(t, 4.0, 12.0)*0.45+ramp(t, 13.0, 20.0)*0.55

def haze(t):            # ground haze multiplier: full in orbit (the blue planet), thinner in the descent
    return 1.0-0.45*ramp(t, 5.0, 10.0)+0.15*ramp(t, 15.0, 19.0)
