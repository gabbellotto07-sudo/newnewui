"""Seliu v5 opening — sound design (procedural, no third-party samples, no music).
Three layers hand over to each other: thin high air -> descent -> sea level.
usage: sound.py out.wav [duration]
"""
import sys, os, numpy as np
from scipy import signal
import timeline as TL

SR = 48000
DUR = float(sys.argv[2]) if len(sys.argv) > 2 else TL.DURATION
N = int(SR*DUR)
t = np.arange(N)/SR
rng = np.random.default_rng(2026)

def noise(kind="white", n=N):
    w = rng.standard_normal(n)
    if kind == "white": return w
    f = np.fft.rfftfreq(n, 1/SR); W = np.fft.rfft(w)
    W[1:] /= (f[1:]**(0.5 if kind == "pink" else 1.0)); W[0] = 0
    x = np.fft.irfft(W, n); return x/np.std(x)

def env(points):
    """piecewise-linear envelope from (time, value) pairs, smoothed"""
    p = np.array(points, float); e = np.interp(t, p[:, 0], p[:, 1])
    return signal.savgol_filter(e, 4801, 2) if N > 4801 else e

def sweep_filter(x, kind, f_of_t, q=0.7, block=1024):
    """time-varying 2nd-order filter, coefficients updated per block (smooth sweeps)"""
    y = np.zeros_like(x); zi = np.zeros((1, 2))
    for i in range(0, len(x), block):
        fc = float(np.clip(f_of_t(i/SR), 20, SR/2.2))
        if kind == "bp":
            bw = fc/q; sos = signal.butter(1, [max(fc-bw/2, 10), min(fc+bw/2, SR/2.1)], "bandpass", fs=SR, output="sos")
        else:
            sos = signal.butter(2, fc, kind, fs=SR, output="sos")
        seg, zi = signal.sosfilt(sos, x[i:i+block], zi=zi if zi.shape == (sos.shape[0], 2) else np.zeros((sos.shape[0], 2)))
        y[i:i+block] = seg
    return y

def lp(x, fc, o=2): return signal.sosfilt(signal.butter(o, fc, "low", fs=SR, output="sos"), x)
def hp(x, fc, o=2): return signal.sosfilt(signal.butter(o, fc, "high", fs=SR, output="sos"), x)
def bp(x, a, b, o=2): return signal.sosfilt(signal.butter(o, [a, b], "bandpass", fs=SR, output="sos"), x)
def pan(x, p):       # p in [-1,1], equal power
    a = (np.asarray(p)+1)*np.pi/4; return np.stack([x*np.cos(a), x*np.sin(a)])
def db(v): return 10**(v/20)

L = np.zeros((2, N))
STEMS = {}; _prev = [np.zeros((2, N)), None]
def _mark(name):
    if _prev[1] is not None: STEMS[_prev[1]] = L-_prev[0]
    _prev[0] = L.copy(); _prev[1] = name

_mark("01_alta_quota_vento")
# 1. high-altitude air: wide, dark, slowly breathing; opens up during the dive
for ch in range(2):
    x = noise("brown")
    cut = lambda s: 220+1400*TL.ramp(s, 8.0, 14.5)*(1-TL.ramp(s, 16.0, 19.5))+180*np.sin(s*0.7+ch)
    y = sweep_filter(x, "low", cut)
    y = y/np.std(y)
    lfo = 1+0.25*np.sin(2*np.pi*t*0.11+ch*1.7)+0.12*np.sin(2*np.pi*t*0.31+ch)
    L[ch] += y*lfo*env([(0, 0), (0.05, 0.3), (3, 0.45), (7.5, 0.55), (11.5, 0.9), (14.2, 1.15), (15.6, 0.6), (19, 0.12), (22.5, 0.05), (DUR, 0.04)])*db(-16)

_mark("02_fischio_aria_rarefatta")
# 2. thin whistle of thin air (barely there)
w = bp(noise(), 2300, 2900, 2); w /= np.std(w)
L += pan(w*env([(0, 0), (0.3, 0.7), (7.5, 0.5), (10.5, 0)])*db(-41), np.sin(t*0.4)*0.6)

_mark("03_jet_lontano_voli")
# 3. a distant airliner while the flights are drawn (left -> right, Singapore arc)
hum = sum(np.sin(2*np.pi*(f*(1+0.004*np.sin(t*0.5)))*t+k)/(k+1) for k, f in enumerate([92, 184, 276, 368]))
jet = bp(noise("pink"), 250, 2400, 2); jet /= np.std(jet)
je = env([(0, 0), (4.0, 0), (5.6, 0.9), (7.4, 0.7), (9.6, 0)])
L += pan((0.6*jet+0.25*hum)*je*db(-29), np.interp(t, [4.0, 9.6], [-0.7, 0.6]))

_mark("04_picchiata_aria")
# 4. the dive: airflow rising in pitch, then easing as we level out
for ch, dl in ((0, 0.0), (1, 0.35)):
    dv = sweep_filter(noise("pink"), "bp", lambda s, dl=dl: 350+2300*TL.ramp(s, 9.5+dl, 14.4)*(1-TL.ramp(s, 14.6, 18.0)), q=1.2)
    dv /= np.std(dv)
    L[ch] += dv*env([(0, 0), (9.5, 0), (13, 0.85), (14.4, 1.0), (15.6, 0.35), (19, 0)])*db(-24)

_mark("05_mare_risacca_reef")
# 5. sea level: surf on the reef (wave events), shore hiss, deep surge
sea = np.zeros((2, N))
starts = 16.2+np.cumsum(rng.uniform(2.6, 4.2, 12))
for k, s0 in enumerate(np.r_[16.2, starts]):
    if s0 > DUR: break
    n0 = int(s0*SR); ln = int(rng.uniform(3.5, 5.0)*SR); n1 = min(N, n0+ln)
    if n1 <= n0: continue
    tt = np.arange(n1-n0)/SR
    e = (1-np.exp(-tt/0.7))*np.exp(-tt/1.6)
    p = rng.uniform(-0.6, 0.6); g = rng.uniform(0.7, 1.0)
    for ch in range(2):
        burst = noise("pink", n1-n0)
        br = sweep_filter(burst, "low", lambda s: 500+2600*np.exp(-((s-0.9)/0.8)**2))
        side = np.cos((p+1)*np.pi/4) if ch == 0 else np.sin((p+1)*np.pi/4)
        sea[ch, n0:n1] += br/np.std(br)*e*g*(0.35+0.65*side)
hiss = hp(noise(), 2500); hiss = lp(hiss, 9000); hiss /= np.std(hiss)
surge = lp(noise("brown"), 140); surge /= np.std(surge)
se = env([(0, 0), (15.6, 0), (19.0, 0.75), (21.5, 1.0), (DUR, 1.0)])
L += sea*se*db(-16)
L += pan(hiss*(0.6+0.4*np.sin(t*0.9)), 0.0)*se*db(-38)
surge2 = lp(noise("brown"), 140); surge2 /= np.std(surge2)
L += np.stack([surge, surge2])*se*db(-27)

_mark("06_brezza_palme")
# 6. breeze in the palms (fast irregular rustle), arrives with the island
rs = bp(noise(), 1800, 7000); rs /= np.std(rs)
am = np.abs(lp(noise(), 6)); am /= am.max()
L += np.stack([rs*am, np.roll(rs*am, 1300)])*env([(0, 0), (18.0, 0), (21.0, 0.8), (DUR, 0.9)])*db(-37)

_mark("07_fuoribordo_traversata")
# 7. a far outboard crossing from Teluk Gembira (right) to Seliu (left) while the route draws
f0 = 58*(1+0.03*np.sin(t*1.3))
ph = 2*np.pi*np.cumsum(f0)/SR
saw = sum(np.sin(k*ph)/k for k in range(1, 18))
putt = 0.55+0.45*np.sin(2*np.pi*9.5*t)**2
mot = bp(saw*putt, 160, 1400, 2); mot /= np.std(mot)
me = env([(0, 0), (19.6, 0), (20.8, 0.8), (22.6, 0.7), (24.2, 0.3), (DUR, 0.2)])
L += pan(mot*me*db(-35), np.interp(t, [19.8, 23.5], [0.55, -0.35]))

_mark("08_sub_sotto_titolo_seliu")
# 8. a low swell under the island's name (felt more than heard)
sw = np.sin(2*np.pi*44*t)*env([(0, 0), (17.0, 0), (18.4, 1), (21.5, 0.35), (DUR, 0.2)])
L += np.stack([sw, sw])*db(-24)


_mark("09_orbita_drone_basso")
# 9. orbit: a slow, vast low drone that opens the film before the picture (felt more than heard)
orb = (np.sin(2*np.pi*36*t)+0.5*np.sin(2*np.pi*54.2*t+1)+0.25*np.sin(2*np.pi*72.5*t+2))
orb = orb*env([(0, 0), (0.05, 0.5), (2.5, 1.0), (6.0, 0.6), (9.0, 0)])
L += np.stack([orb, np.roll(orb, 900)])*db(-27)
_mark("10_passaggio_nuvole_whoosh")
# 10. passing over the cumulus field: two soft airy whooshes, left then right
for c0, pn in ((15.3, -0.5), (16.4, 0.45)):
    wv = sweep_filter(noise("pink"), "bp", lambda s, c0=c0: 500+1800*np.exp(-((s-c0)/0.45)**2), q=1.5)
    wv /= np.std(wv)
    L += pan(wv*env([(0, 0), (c0-0.9, 0), (c0, 1.0), (c0+1.1, 0), (DUR, 0)])*db(-30), pn)

_mark(None)
# master: gentle low cut, soft limiter, -1 dBFS ceiling
L = hp(L, 28, 2)
import soundfile as sf, pyloudnorm as pyln
TARGET = -20.0                       # LUFS: leaves headroom for the music chosen later
L *= np.clip(t/0.05, 0, 1)
lufs = pyln.Meter(SR).integrated_loudness(L.T); L *= db(TARGET-lufs)
gain = db(TARGET-lufs)
if os.environ.get("SELIU_STEMS"):
    d = os.environ["SELIU_STEMS"]; os.makedirs(d, exist_ok=True)
    for k, v in STEMS.items():
        v = hp(v, 28, 2)*np.clip(t/0.05, 0, 1)*gain
        sf.write(os.path.join(d, f"{k}.wav"), v.T.astype(np.float32), SR, subtype="PCM_24")
L = np.tanh(L/db(-3))*db(-3)         # soft ceiling at -3 dBFS
sf.write(sys.argv[1], L.T.astype(np.float32), SR, subtype="PCM_24")
print("wrote", sys.argv[1], f"{DUR}s")
