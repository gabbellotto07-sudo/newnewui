"""Seliu v9 — sound_v8 with the v9 corrections: much less energy under 200 Hz in the first half (the orbit tone
keeps only its upper partials, the descent wind is high-passed until the dive), real high-altitude air on top
(Mixkit recordings, high-passed: thin, rarefied, stereo), same breath before Seliu, the boat on the v9 wake.
(v8 header follows)
Seliu v8 — ambience and sound design from real recordings (Mixkit / Freesound CC0), with a light
synthetic layer only to bind. No music: room is left for it (ambience ~-20 LUFS, 200 Hz-2 kHz kept clear).

Arc (follows timeline_v8, nothing hand-timed that the camera already knows):
  orbit      near silence: thin high air + a low tone made audible on phones by its harmonics
  descent    real wind that grows with the camera's real speed through denser air; the filter opens,
             a slight Doppler; stereo passes when the camera crosses the cloud layer
  arrival    a real breath (~0.8 s) right before Seliu appears, then the sea opens wide: surf on the reef
  crossing   a distant outboard moving right -> left with the boat
  graphics   small organic touches (air, paper) under the ambience, never beeps
usage: sound_v8.py OUTDIR [--fmt 16x9|9x16] -> mix + stems (48 kHz / 24 bit)
"""
import sys, os, json, math, argparse
import numpy as np, soundfile as sf
from scipy import signal
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
SR = 48000
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(os.path.dirname(ROOT), "audio", "src")
rng = np.random.default_rng(828)

def load(name, start=0.0, dur=None):
    x, sr = sf.read(os.path.join(SRC, name), always_2d=True)
    x = x.astype(np.float64)
    if x.shape[1] == 1: x = np.repeat(x, 2, 1)
    if sr != SR:
        g = math.gcd(SR, sr); x = signal.resample_poly(x, SR//g, sr//g, axis=0)
    a = int(start*SR); b = len(x) if dur is None else min(len(x), a+int(dur*SR))
    return x[a:b]

def loop_to(x, n, xfade=2.0):
    """loop a bed to n samples with equal-power crossfades (no audible seam)"""
    if len(x) >= n: return x[:n]
    f = int(xfade*SR); out = x.copy()
    while len(out) < n:
        w = np.sin(np.linspace(0, np.pi/2, f))[:, None]
        out = np.concatenate([out[:-f], out[-f:]*np.cos(np.linspace(0, np.pi/2, f))[:, None]+x[:f]*w, x[f:]])
    return out[:n]

def sos(kind, f, order=2): return signal.butter(order, f, kind, fs=SR, output="sos")
def filt(x, kind, f, order=2): return signal.sosfiltfilt(sos(kind, f, order), x, axis=0)

def sweep(x, kind, fc_t, block=512):
    """time-varying low/high-pass (2nd order), coefficients per block, zero-state carried"""
    y = np.zeros_like(x); zi = None
    for i in range(0, len(x), block):
        s = sos(kind, float(np.clip(fc_t[min(i, len(fc_t)-1)], 30, SR/2.3)))
        if zi is None: zi = np.zeros((s.shape[0], 2, x.shape[1]))
        seg, zi = signal.sosfilt(s, x[i:i+block], axis=0, zi=zi)
        y[i:i+block] = seg
    return y

def env_pts(n, pts, smooth=0.25):
    t = np.arange(n)/SR; p = np.array(pts, float)
    e = np.interp(t, p[:, 0], p[:, 1])
    if smooth > 0:
        k = int(smooth*SR) | 1; e = signal.fftconvolve(np.pad(e, k//2, mode="edge"), np.hanning(k)/np.hanning(k).sum(), "valid")
    return e

def pan(x, p):
    """equal-power pan, p in -1..1 (array per sample or scalar), on a stereo signal"""
    p = np.asarray(p, float)
    a = (p+1)*np.pi/4
    m = x.mean(1)
    side = (x[:, 0]-x[:, 1])/2
    l = m*np.cos(a)*np.sqrt(2)+side*0.6; r = m*np.sin(a)*np.sqrt(2)-side*0.6
    return np.stack([l, r], 1)

def width(x, w):
    m = (x[:, 0]+x[:, 1])/2; s = (x[:, 0]-x[:, 1])/2*np.asarray(w)
    return np.stack([m+s, m-s], 1)

def db(v): return 10**(v/20)

def camera_curves(n, fmt):
    """per-sample curves derived from the real camera path: speed through the air, altitude, cloud proximity"""
    os.environ["SELIU_FMT"] = fmt
    import importlib, timeline_v9 as TL; importlib.reload(TL)
    from render import ecef
    ts = np.arange(0, TL.DURATION+0.04, 0.04)
    P = []; alt = []
    for t in ts:
        lat, lon, rng_m, hd, tl, rl = TL.camera(t)
        import render_v9 as R
        c = R.Camera(lat, lon, rng_m, hd, tl, TL.VFOV, 16, 9, roll=rl)
        P.append(c.pos); alt.append(c.alt)
    P = np.array(P); alt = np.array(alt)
    v = np.r_[0, np.linalg.norm(np.diff(P, axis=0), axis=1)/0.04]
    # perceived airspeed: ground speed scaled by the air density at the camera's height (thin air is quiet)
    rho = np.exp(-alt/8000.0)
    air = np.log1p(v/50.0)*(0.15+0.85*rho**0.35)
    zoom = np.abs(np.gradient(np.log(np.maximum(alt, 1.0)), ts))       # how fast the world rushes up
    t_s = np.arange(n)/SR
    f = lambda y: np.interp(t_s, ts, y)
    return dict(air=f(air/np.max(air)), zoom=f(zoom/np.max(zoom)), alt=f(alt), dur=TL.DURATION, TL=TL)

def build(fmt="16x9"):
    os.environ["SELIU_FMT"] = fmt
    import timeline_v9 as TL
    N = int(TL.DURATION*SR); t = np.arange(N)/SR
    cv = camera_curves(N, fmt)
    stems = {}
    # ---------------------------------------------------------------- 1. high air (orbit -> region)
    hi = loop_to(load("mk_1267.wav", 1.0), N)                         # wind at a mountain top, thinned
    hi = filt(hi, "highpass", 1200); hi = filt(hi, "lowpass", 12000)
    e = env_pts(N, [(0, 0.0), (0.4, 0.6), (4, 0.75), (8, 0.6), (11, 0.35), (14.5, 0.0), (28, 0)], 0.6)
    stems["air_high"] = width(hi, 1.15)*e[:, None]*db(-3)
    # v9: rarefied air in altitude: two real wind recordings, only their hiss (> 2.5 kHz), wide and slow
    r1 = loop_to(load("mk_1201.wav", 2.0), N); r2 = loop_to(load("mk_2495.wav", 5.0), N)
    rare = filt(0.7*r1+0.6*r2, "highpass", 2500, 3); rare = filt(rare, "lowpass", 11000)
    rare *= (1+0.25*np.sin(2*np.pi*0.09*t+0.6))[:, None]                # a slow breathing of the air
    e = env_pts(N, [(0, 0.0), (0.5, 0.7), (3, 1.0), (9, 0.85), (13, 0.5), (16.6, 0.25), (17.1, 0.0), (28, 0)], 0.7)
    stems["air_rare"] = width(rare, 1.15)*e[:, None]*db(-15)
    # orbit tone: a low A with its harmonics (audible on a phone through the 2nd-4th partials), very slow swell
    f0 = 55.0
    # v9: the 55 and 110 Hz partials are gone (too much low end in the first half); the ear still hears the
    # low A from the upper harmonics (missing fundamental), and a phone speaker can play it
    tone = sum(a*np.sin(2*np.pi*f0*k*t+ph) for k, a, ph in ((3, 0.62, 2.3), (4, 0.52, 0.7), (5, 0.38, 2.9), (6, 0.28, 1.9), (8, 0.16, 0.4), (10, 0.08, 1.3)))
    tone = np.tanh(1.6*tone)/np.tanh(1.6)                                # gentle saturation: more harmonics
    tone *= 1+0.06*np.sin(2*np.pi*0.13*t)
    e = env_pts(N, [(0, 0.0), (0.3, 0.6), (3, 1.0), (7, 0.8), (10.5, 0.35), (13.5, 0.0), (28, 0)], 0.8)
    tone = filt(tone, "highpass", 150)
    stems["orbit_tone"] = np.stack([tone, np.roll(tone, 37)], 1)*e[:, None]*db(-34)
    # ---------------------------------------------------------------- 2. descent wind, driven by the camera
    w1 = loop_to(load("mk_1172.wav"), N); w2 = loop_to(load("mk_2658.wav", 3.0), N); w3 = loop_to(load("mk_1200.wav"), N)
    wind = filt(0.55*w1+0.6*w2+0.35*w3, "highpass", 120)
    # v9: until the dive the low wind rumble is cut (high-pass 260 Hz), then it opens to 120 Hz
    lowpart = wind-filt(wind, "highpass", 260)
    wind = wind-lowpart*(1-env_pts(N, [(0, 0), (13.0, 0), (15.0, 1), (28, 1)], 0.3))[:, None]
    air = cv["air"]
    g = np.clip(air, 0, 1)**1.3
    fc = 350+5200*np.clip(air*1.15, 0, 1)**1.6                       # the filter opens with speed
    wind = sweep(wind, "low", fc)
    # Doppler-ish: tiny resampling drift following the acceleration (a few cents, felt not heard)
    acc = np.gradient(air)*SR
    rate = 1+np.clip(acc, -0.3, 0.3)*0.004
    pos = np.cumsum(rate); pos = pos/pos[-1]*(N-1)
    wind = np.stack([np.interp(pos, np.arange(N), wind[:, c]) for c in range(2)], 1)
    e = env_pts(N, [(0, 0), (4, 0.2), (8, 0.5), (11, 0.55), (12.6, 0.45), (14.2, 0.9), (16.2, 1.0), (16.9, 0.5), (17.25, 0.0), (28, 0)], 0.35)
    stems["wind_descent"] = width(wind, 1.2)*(g*e)[:, None]*db(-6)
    # cloud layer: air torn as the camera skims the cumulus field (stereo passes, panned with the clouds)
    for tc, p0, p1, gdb in ((15.1, -0.8, 0.9, -11), (16.0, 0.7, -0.9, -10)):
        x = load("mk_2705.wav")
        x = filt(x, "highpass", 250); x = filt(x, "lowpass", 6000)
        n = len(x); a = int((tc-0.6)*SR)
        ee = np.hanning(n)**0.8
        pp = np.linspace(p0, p1, n)
        seg = pan(x, pp)*ee[:, None]*db(gdb)
        b = min(N, a+n); stems.setdefault("cloud_pass", np.zeros((N, 2)))[a:b] += seg[:b-a]
    # ---------------------------------------------------------------- 3. the breath, then the sea opens
    breath_a, breath_b = 17.0, 17.85                                    # ~0.85 s of held air before Seliu
    sea1 = loop_to(load("mk_1206.wav", 10.0), N); sea2 = loop_to(load("mk_1189.wav", 20.0), N)
    reef = loop_to(load("mk_1208.wav", 5.0), N)
    sea = 0.7*sea1+0.5*sea2
    sea = filt(sea, "highpass", 150, 3)
    e = env_pts(N, [(0, 0), (breath_b-0.05, 0.0), (breath_b+0.9, 0.85), (20, 1.0), (28, 1.0)], 0.3)
    w = env_pts(N, [(0, 0.6), (breath_b, 0.6), (breath_b+2.5, 1.2), (28, 1.2)], 0.5)        # opens in stereo (v9: mono-safe)
    stems["sea"] = width_curve(sea, w)*e[:, None]*db(-9)
    e = env_pts(N, [(0, 0), (breath_b+0.4, 0.0), (breath_b+1.8, 0.9), (28, 1.0)], 0.4)
    stems["reef"] = width(filt(reef, "highpass", 300), 1.1)*e[:, None]*db(-8)
    breeze = loop_to(load("mk_2427.wav"), N)
    breeze = filt(breeze, "lowpass", 5000)
    e = env_pts(N, [(0, 0), (breath_b+1.0, 0.0), (breath_b+3, 0.7), (28, 0.8)], 0.5)
    stems["breeze"] = width(breeze, 1.2)*e[:, None]*db(-20)
    # the breath itself: everything else ducks; a held, very soft air keeps it from sounding like a gap
    duck = 1-0.92*env_pts(N, [(0, 0), (breath_a-0.15, 0), (breath_a+0.1, 1), (breath_b-0.1, 1), (breath_b+0.35, 0), (28, 0)], 0.12)
    held = filt(loop_to(load("mk_1275.wav", 4.0), N), "lowpass", 2500)
    e = env_pts(N, [(0, 0), (breath_a-0.2, 0), (breath_a+0.15, 1), (breath_b, 0.8), (breath_b+0.6, 0), (28, 0)], 0.1)
    stems["breath_air"] = width(held, 0.8)*e[:, None]*db(-14)
    # ---------------------------------------------------------------- 4. the boat, far, right -> left
    T = TL_times(fmt)
    boat = load("mk_1183.wav", 4.0, T["boat_b"]-T["boat_a"]+3.0)
    boat = filt(boat, "highpass", 140); boat = filt(boat, "lowpass", 2600)
    n = len(boat); a = int((T["boat_a"]-0.8)*SR); b = min(N, a+n)
    ee = env_pts(n, [(0, 0), (1.2, 0.8), (n/SR-2.0, 0.9), (n/SR, 0.0)], 0.4)
    pp = np.linspace(0.75, -0.6, n) if fmt == "16x9" else np.linspace(0.15, -0.1, n)
    seg = pan(boat, pp)*ee[:, None]*db(-17)
    # a touch of distance: early reflections off the water
    for dly, gg in ((0.031, 0.35), (0.067, 0.22)):
        k = int(dly*SR); seg[k:] += seg[:-k]*gg
    stems["boat"] = np.zeros((N, 2)); stems["boat"][a:b] = seg[:b-a]
    # ---------------------------------------------------------------- 5. graphics: organic, under everything
    stems["gfx"] = gfx_layer(N, fmt)
    # ---------------------------------------------------------------- mix
    for k in stems:
        if k != "breath_air": stems[k] = stems[k]*duck[:, None]
    return stems

def width_curve(x, w):
    m = (x[:, 0]+x[:, 1])/2; s = (x[:, 0]-x[:, 1])/2*w
    return np.stack([m+s, m-s], 1)

def TL_times(fmt):
    import motion_gfx_v9 as M
    return dict(boat_a=M.T["wake"][0], boat_b=M.T["wake"][1])

def gfx_layer(N, fmt):
    """tiny touches of real paper and air on the titles and dots, from motion_gfx's own timing"""
    import motion_gfx_v9 as M
    out = np.zeros((N, 2))
    paper = filt(load("mk_1530.wav"), "highpass", 400)
    airp = filt(load("mk_2604.wav"), "highpass", 300)
    cues = getattr(M, "SOUND_CUES", [])
    for c in cues:
        src = paper if c["kind"] == "title" else airp
        g = db(c.get("db", -30)); p = c.get("pan", 0.0)*(1 if fmt == "16x9" else 0.5)
        x = pan(src, p)*g
        a = int(c["t"]*SR); b = min(N, a+len(x)); out[a:b] += x[:b-a]
    return out

def master(stems, target=-20.0):
    import pyloudnorm as pyln
    mix = sum(stems.values())
    # leave room for the melody: a broad, gentle dip 250 Hz-1.8 kHz on the ambience bus
    b, a = signal.iirpeak(700/(SR/2), 0.55)
    dip = mix-0.30*signal.filtfilt(b, a, mix, axis=0)
    meter = pyln.Meter(SR)
    L = meter.integrated_loudness(dip)
    g = db(target-L)
    return dip*g, g

def glue(mix, thr_db=-30.0, ratio=2.2, win=0.35):
    """slow RMS compression of the whole bed: lifts the quiet orbit relative to the sea, gently"""
    m = (mix**2).mean(1); k = int(win*SR)
    rms = np.sqrt(signal.fftconvolve(m, np.ones(k)/k, "same").clip(1e-12))
    lv = 20*np.log10(rms)
    over = np.maximum(lv-thr_db, 0)
    g = -over*(1-1/ratio)
    g = signal.fftconvolve(g, np.hanning(int(0.2*SR))/np.hanning(int(0.2*SR)).sum(), "same")
    return mix*db(g)[:, None]

def limit(mix, ceiling_db=-1.2, look=0.004, rel=0.08):
    """true-peak-safe limiter: 4x oversampled peaks, look-ahead gain with smooth release"""
    up = signal.resample_poly(mix, 4, 1, axis=0)
    pk = np.abs(up).max(1).reshape(-1, 4).max(1)[:len(mix)]
    c = db(ceiling_db)
    need = np.minimum(1.0, c/np.maximum(pk, 1e-9))
    k = int(look*SR)
    need = -np.maximum.accumulate(-np.r_[need[k:], np.ones(k)]) if False else need
    from scipy.ndimage import minimum_filter1d
    g = minimum_filter1d(need, size=2*k+1)
    a = np.exp(-1/(rel*SR)); out = np.empty_like(g); cur = 1.0
    for i in range(len(g)):                                   # instant attack, smooth release
        cur = g[i] if g[i] < cur else g[i]+(cur-g[i])*a
        out[i] = cur
    return mix*out[:, None]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("--fmt", default="16x9")
    ap.add_argument("--target", type=float, default=-20.0)
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    stems = build(a.fmt)
    import pyloudnorm as pyln
    mix, g = master(stems, a.target)
    mix = glue(mix)
    meter = pyln.Meter(SR)
    for _ in range(3):                                       # loudness to target, true peak under -1 dBTP
        mix = mix*db(a.target-meter.integrated_loudness(mix)); mix = limit(mix)
    g = g*float(np.sqrt(np.mean(mix**2))/max(np.sqrt(np.mean(sum(stems.values())**2))*g, 1e-12))
    sf.write(os.path.join(a.out, f"ambience_{a.fmt}.wav"), mix.astype(np.float32), SR, subtype="PCM_24")
    for k, v in stems.items():
        sf.write(os.path.join(a.out, f"stem_{a.fmt}_{k}.wav"), (v*g).astype(np.float32), SR, subtype="PCM_24")
    print("written", a.out, "gain", round(20*np.log10(g), 1), "dB")

if __name__ == "__main__":
    main()
