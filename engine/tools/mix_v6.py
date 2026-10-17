"""v6 master mix: ambience (v5) + graphics SFX (v6) -> -16 LUFS (web), soft ceiling -1.5 dBFS. Also keeps both stems."""
import numpy as np, soundfile as sf, pyloudnorm as pl
a, sr = sf.read("audio/sfx_v5.wav"); b, _ = sf.read("audio/sfx_gfx_v6.wav")
n = max(len(a), len(b)); A = np.zeros((n, 2)); A[:len(a)] += a; A[:len(b)] += b
l = pl.Meter(sr).integrated_loudness(A); A *= 10**((-16-l)/20)
c = 10**(-1.5/20); A = np.tanh(A/c)*c
sf.write("audio/mix_v6_master.wav", A.astype(np.float32), sr, subtype="PCM_24")
print("LUFS", round(pl.Meter(sr).integrated_loudness(A), 1), "peak", round(20*np.log10(np.abs(A).max()), 1))
