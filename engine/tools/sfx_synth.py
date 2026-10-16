"""Procedural synthesis of the graphic SFX cues (tools/sfx_cues.json) -> 48 kHz stereo 24-bit WAV, 25 s.

No samples, no third-party sounds: sines, filtered noise, envelopes and a synthetic room.
Tone: documentary, delicate, low level (meant to sit under the v5 ambience and the client's music).

usage: python3 tools/sfx_synth.py [out.wav]    (default audio/sfx_gfx_v6.wav)
"""
import os, sys, json, math
import numpy as np
from scipy.signal import butter, sosfilt, fftconvolve
import soundfile as sf, pyloudnorm as pyln

SR = 48000
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def env_adsr(n, a, r, shape=2.0):
    """attack a (s) then exponential-ish release to the end"""
    t = np.arange(n)/SR; na = max(int(a*SR), 1)
    e = np.ones(n)
    e[:na] = np.sin(np.linspace(0, np.pi/2, na))**2
    rel = np.clip((t-a)/max(n/SR-a, 1e-3), 0, 1)
    return e*(1-rel)**shape

def hann_env(n, peak=0.5):
    x = np.linspace(0, 1, n); p = peak
    return np.where(x < p, np.sin(np.pi/2*x/p)**2, np.cos(np.pi/2*(x-p)/(1-p))**2)

def bp(x, lo, hi, order=4):
    return sosfilt(butter(order, [lo, hi], btype="band", fs=SR, output="sos"), x)

def lp(x, f, order=2): return sosfilt(butter(order, f, btype="low", fs=SR, output="sos"), x)
def hp(x, f, order=2): return sosfilt(butter(order, f, btype="high", fs=SR, output="sos"), x)

def svf_lp(x, fc):
    """time-varying 2-pole state-variable low-pass (fc per sample)"""
    y = np.empty_like(x); low = band = 0.0; q = 0.7
    f = 2*np.sin(np.pi*np.clip(fc, 20, SR/7)/SR)
    for i in range(len(x)):
        low += f[i]*band; high = x[i]-low-q*band; band += f[i]*high; y[i] = low
    return y

def pan2(x, p):
    """equal-power pan; p scalar or array in -1..1"""
    p = np.clip(np.asarray(p, float), -1, 1); a = (p+1)*np.pi/4
    return np.stack([x*np.cos(a), x*np.sin(a)], -1)

def norm(x):
    m = np.max(np.abs(x)); return x/m if m > 0 else x

# ------------------------------------------------------------------ voices
def v_glint(n, rng, pitch=1.0, **_):
    t = np.arange(n)/SR; f0 = 1318.5*pitch                     # E6, inharmonic bell partials
    y = np.zeros(n)
    for r, a, d in ((1.0, 1.0, 0.42), (2.76, 0.35, 0.22), (5.40, 0.12, 0.12), (1.5, 0.25, 0.30)):
        y += a*np.sin(2*np.pi*f0*r*t+rng.uniform(0, 6))*np.exp(-t/d)
    att = np.clip(t/0.004, 0, 1)
    tr = hp(rng.standard_normal(n), 5000)*np.exp(-t/0.006)*0.25
    return norm(y*att+tr)

def v_letters_air(n, rng, letters=8, **_):
    k = letters
    t = np.arange(n)/SR; y = np.zeros(n)
    base = bp(rng.standard_normal(n), 2500, 9000)
    for i in range(k):                                         # one soft grain per letter, staggered
        c = 0.08+0.55*i/max(k-1, 1)+rng.uniform(-0.02, 0.02); w = 0.09
        y += base*np.exp(-0.5*((t-c)/w)**2)*rng.uniform(0.6, 1.0)
    return norm(y*hann_env(n, 0.35))

def v_wipe_breath(n, rng, **_):
    x = rng.standard_normal(n)
    fc = np.geomspace(700, 3800, n)
    y = svf_lp(x, fc)-0.6*svf_lp(x, fc*0.35)
    return norm(y*hann_env(n, 0.45))

def v_line_shimmer(n, rng, low=False, seed=None, **_):
    r2 = np.random.default_rng(seed) if seed is not None else rng
    t = np.arange(n)/SR; y = np.zeros(n)
    lo, hi = (900, 2600) if low else (2600, 6200)
    for _ in range(14):
        f = r2.uniform(lo, hi); ph = r2.uniform(0, 6.3)
        am = 0.5+0.5*np.sin(2*np.pi*r2.uniform(3, 11)*t+r2.uniform(0, 6.3))
        y += np.sin(2*np.pi*f*t+0.002*f*np.sin(2*np.pi*5*t)+ph)*am*r2.uniform(0.3, 1.0)
    air = bp(r2.standard_normal(n), lo*1.2, min(hi*1.8, 16000))*1.5
    e = hann_env(n, 0.62)                                      # grows with the line, peaks near arrival
    return norm((0.70*y/14+0.30*norm(air))*e)

def v_arrival_tick(n, rng, **_):
    t = np.arange(n)/SR
    y = np.sin(2*np.pi*880*t)*np.exp(-t/0.05)+0.5*bp(rng.standard_normal(n), 1500, 6000)*np.exp(-t/0.008)
    return norm(y*np.clip(t/0.002, 0, 1))

def v_dissolve(n, rng, **_):
    x = rng.standard_normal(n)
    fc = np.geomspace(5200, 500, n)
    return norm(svf_lp(x, fc)*hann_env(n, 0.2))

def v_title_swell(n, rng, root=110.0, **_):
    t = np.arange(n)/SR
    pad = sum(a*np.sin(2*np.pi*root*r*t*(1+0.0015*np.sin(2*np.pi*0.3*t+r))) for r, a in ((1, 1.0), (1.5, 0.55), (2, 0.45), (3, 0.18)))
    pad = lp(pad, 900)*hann_env(n, 0.38)
    air = svf_lp(rng.standard_normal(n), 300+2600*hann_env(n, 0.35))*hann_env(n, 0.3)
    return norm(0.65*norm(pad)+0.35*norm(air))

def v_rule_tick(n, rng, **_):
    t = np.arange(n)/SR
    y = np.sin(2*np.pi*3520*t)*np.exp(-t/0.06)*0.6+bp(rng.standard_normal(n), 6000, 12000)*np.exp(-t/0.02)*0.3
    sweep = bp(rng.standard_normal(n), 3000, 9000)*hann_env(n, 0.5)*0.25
    return norm(y+sweep)

def v_riser(n, rng, **_):
    t = np.arange(n)/SR; u = t/t[-1]
    amp = (np.exp(3.2*u)-1)/(math.e**3.2-1)
    amp *= np.clip((1-u)/0.04, 0, 1)                           # tucks under the bloom, no hit
    noise = svf_lp(rng.standard_normal(n), 380*np.exp(np.log(5200/380)*u))
    f = 220*np.exp(np.log(1.5)*u**1.5)
    tone = np.sin(2*np.pi*np.cumsum(f)/SR)+0.35*np.sin(2*np.pi*np.cumsum(f*1.5)/SR)
    return norm((0.7*norm(noise)+0.3*tone)*amp)

def v_outline_shimmer(n, rng, **_):
    """granular high bells (A major pentatonic), density follows the draw speed (in-out cubic)"""
    t = np.arange(n)/SR; u = t/t[-1]
    scale = [1760.0, 1975.5, 2217.5, 2637.0, 2960.0, 3520.0]
    L = np.zeros(n); R = np.zeros(n)
    speed = 1-np.abs(2*u-1)                                    # draw speed of in-out easing ~ peak mid
    cnt = 0; tt = 0.0
    while tt < t[-1]-0.05:
        i0 = int(tt*SR); d = 0.5; m = min(int(d*SR), n-i0); tg = np.arange(m)/SR
        f = scale[rng.integers(len(scale))]
        g = (np.sin(2*np.pi*f*tg)+0.3*np.sin(2*np.pi*f*2.76*tg))*np.exp(-tg/0.18)*np.clip(tg/0.003, 0, 1)
        g *= rng.uniform(0.4, 1.0)
        (L if cnt % 2 == 0 else R)[i0:i0+m] += g               # the two heads, one per side
        cnt += 1
        tt += 0.035+0.20*(1-speed[min(i0, n-1)])
    air = bp(rng.standard_normal(n), 3000, 11000)*hann_env(n, 0.5)*0.6
    e = hann_env(n, 0.55)
    return np.stack([norm(L)*0.7+air, norm(R)*0.7+air], -1)*e[:, None]

def v_flash_bloom(n, rng, **_):
    t = np.arange(n)/SR
    ch = [220.0, 329.6, 440.0, 554.4, 659.3]
    y = sum(np.sin(2*np.pi*f*t+rng.uniform(0, 6))*a for f, a in zip(ch, (1, .7, .6, .45, .3)))
    y = lp(y, 2400)*env_adsr(n, 0.12, 0, 2.6)
    sh = bp(rng.standard_normal(n), 4000, 12000)*env_adsr(n, 0.02, 0, 4)*0.25
    return norm(y+sh)

def v_glint_pass(n, rng, **_):
    t = np.arange(n)/SR
    y = sum(np.sin(2*np.pi*f*t*(1+0.002*np.sin(2*np.pi*4*t)))*a for f, a in ((2637, 1), (3520, .6), (5274, .25)))
    return norm(y*hann_env(n, 0.5)*(0.6+0.4*np.sin(2*np.pi*7*t)**2))

VOICES = dict(glint=v_glint, letters_air=v_letters_air, wipe_breath=v_wipe_breath, line_shimmer=v_line_shimmer,
              arrival_tick=v_arrival_tick, dissolve=v_dissolve, title_swell=v_title_swell, rule_tick=v_rule_tick,
              riser=v_riser, outline_shimmer=v_outline_shimmer, flash_bloom=v_flash_bloom, glint_pass=v_glint_pass)
WET = dict(glint=0.35, letters_air=0.2, wipe_breath=0.2, line_shimmer=0.3, arrival_tick=0.3, dissolve=0.3,
           title_swell=0.35, rule_tick=0.35, riser=0.25, outline_shimmer=0.4, flash_bloom=0.45, glint_pass=0.45)

def room(rng, sec=2.2):
    n = int(sec*SR); t = np.arange(n)/SR
    ir = rng.standard_normal((n, 2))*np.exp(-t/0.45)[:, None]
    ir = np.stack([lp(hp(ir[:, c], 300), 7000) for c in range(2)], -1)
    ir[:int(0.012*SR)] = 0                                     # pre-delay
    return ir/np.sqrt((ir**2).sum(0))

def render(cues_path, out_path):
    spec = json.load(open(cues_path)); dur = spec["duration_s"]
    N = int(dur*SR); dry = np.zeros((N, 2)); send = np.zeros((N, 2))
    rng = np.random.default_rng(2026)
    for c in spec["cues"]:
        n = int(c["duration_s"]*SR); pr = dict(c.get("params", {}))
        v = VOICES[c["type"]](n, rng, **pr)
        g = 10**(c["level_db"]/20)
        if v.ndim == 1:
            p0 = c["pan"]; p1 = pr.get("pan_end", p0)
            st = pan2(v, np.linspace(p0, p1, n))
        else:
            sp = pr.get("spread", 0.4); p = c["pan"]
            st = pan2(v[:, 0], p-sp)+pan2(v[:, 1], p+sp)
        st = st*g
        i0 = int(c["time_s"]*SR); i1 = min(i0+n, N)
        dry[i0:i1] += st[:i1-i0]; send[i0:i1] += st[:i1-i0]*WET[c["type"]]
    wet = np.stack([fftconvolve(send[:, c], room(rng)[:, c])[:N] for c in range(2)], -1)
    mix = dry+wet
    mix = lp(hp(mix.T, 60).T.T, 9000, 4).T     # soft top: no hiss above ~9 kHz
    meter = pyln.Meter(SR)
    lufs = meter.integrated_loudness(mix)
    mix = mix*10**((spec.get("loudness_target_lufs", -26.0)-lufs)/20)
    pk = np.max(np.abs(mix))
    if pk > 10**(-3/20): mix *= 10**(-3/20)/pk                  # peak ceiling -3 dBFS
    fade = np.ones(N); fl = int(0.02*SR); fade[-fl:] = np.linspace(1, 0, fl)
    mix *= fade[:, None]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    sf.write(out_path, mix.astype(np.float32), SR, subtype="PCM_24")
    print(out_path, "LUFS %.1f -> %.1f, peak %.1f dBFS" % (lufs, meter.integrated_loudness(mix), 20*np.log10(np.max(np.abs(mix)))))

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "audio", "sfx_gfx_v6.wav")
    render(os.path.join(ROOT, "tools", "sfx_cues.json"), out)
