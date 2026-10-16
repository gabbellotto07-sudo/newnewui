"""60 s ambience beds for the raw library (loopable-ish, -23 LUFS): high altitude air, sea on the reef."""
import sys, os, numpy as np, soundfile as sf, pyloudnorm as pyln
from scipy import signal
SR = 48000; D = 60; N = SR*D; t = np.arange(N)/SR; rng = np.random.default_rng(7)
def brown(n): x = np.cumsum(rng.standard_normal(n)); x = signal.sosfilt(signal.butter(1, 20, "high", fs=SR, output="sos"), x); return x/np.std(x)
def pink(n):
    f = np.fft.rfftfreq(n, 1/SR); W = np.fft.rfft(rng.standard_normal(n)); W[1:] /= np.sqrt(f[1:]); W[0] = 0; x = np.fft.irfft(W, n); return x/np.std(x)
lp = lambda x, fc: signal.sosfilt(signal.butter(2, fc, "low", fs=SR, output="sos"), x)
bp = lambda x, a, b: signal.sosfilt(signal.butter(2, [a, b], "bandpass", fs=SR, output="sos"), x)
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
def norm(x, target):
    x = x*np.minimum(1, np.minimum(t/0.5, (D-t)/0.5))[None]
    l = pyln.Meter(SR).integrated_loudness(x.T); return x*10**((target-l)/20)
# high altitude: dark wind, slow breathing, independent L/R
A = np.stack([lp(brown(N), 320)*(1+0.3*np.sin(2*np.pi*0.07*t+k*2)) for k in range(2)])
sf.write(f"{out}/bed_alta_quota_60s.wav", norm(A, -23).T.astype(np.float32), SR, subtype="PCM_24")
# sea on the reef: wave events per channel + hiss + surge
S = np.zeros((2, N))
for ch in range(2):
    s0 = 0.0
    while s0 < D:
        n0 = int(s0*SR); ln = int(rng.uniform(3.5, 5)*SR); n1 = min(N, n0+ln); tt = np.arange(n1-n0)/SR
        e = (1-np.exp(-tt/0.7))*np.exp(-tt/1.6); b = lp(pink(n1-n0), 1800); S[ch, n0:n1] += b/np.std(b)*e*rng.uniform(0.6, 1)
        s0 += rng.uniform(2.6, 4.2)
    S[ch] += 0.25*bp(rng.standard_normal(N), 2500, 9000)/1.0 + 0.5*lp(brown(N), 140)
sf.write(f"{out}/bed_mare_reef_60s.wav", norm(S, -23).T.astype(np.float32), SR, subtype="PCM_24")
print("beds written")
