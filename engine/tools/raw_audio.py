"""Seliu v9 raw — audio for the 41 s raw (t = -3 ... 38): sound_v9 stems (38 s, from t = 0) shifted by 3 s, with a
3 s pre-roll of thin real high air (Mixkit 1267) that fades in under the stars and hands over to the orbit air.
Writes 48 kHz / 24-bit: ambiente.wav, effetti.wav, mix.wav (= ambiente + effetti, -20 LUFS, <= -1 dBTP: room
for music), and every stem. usage: raw_audio.py STEMS_DIR (sound_v9 output, --target -20) OUT_DIR"""
import sys, os, numpy as np, soundfile as sf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sound_v9 as S
SR = S.SR
AMB = ["air_high", "air_rare", "wind_descent", "sea", "reef", "breeze"]
FX = ["cloud_pass", "boat", "breath_air"]

def main():
    src, out = sys.argv[1:3]; os.makedirs(os.path.join(out, "stem"), exist_ok=True)
    pre = int(3.0*SR)
    st = {k: sf.read(os.path.join(src, f"stem_16x9_{k}.wav"), always_2d=True)[0] for k in AMB+FX}
    n = pre+len(next(iter(st.values())))
    shift = lambda x: np.concatenate([np.zeros((pre, 2)), x])[:n]
    st = {k: shift(v) for k, v in st.items()}
    air = S.loop_to(S.load("mk_1267.wav", 3.0), n)
    air = S.filt(S.filt(air, "highpass", 1200), "lowpass", 7000)
    e = S.env_pts(n, [(0, 0), (2.2, 0.8), (3.0, 1.0), (4.2, 0.0)], 0.5)
    ref = st["air_high"][int(4.5*SR):int(5.5*SR)]
    lvl = np.sqrt(np.mean(ref**2))+1e-9
    st["air_preroll"] = air/np.sqrt(np.mean(air**2))*lvl*0.8*e[:, None]
    amb = sum(st[k] for k in AMB+["air_preroll"]); fx = sum(st[k] for k in FX)
    mix = amb+fx
    import pyloudnorm as pyln
    m = pyln.Meter(SR); g = S.db(-20.0-m.integrated_loudness(mix))
    mixl = S.limit(mix*g, ceiling_db=-1.2)
    w = lambda p, x: sf.write(os.path.join(out, p), x.astype(np.float32), SR, subtype="PCM_24")
    w("mix.wav", mixl); w("ambiente.wav", amb*g); w("effetti.wav", fx*g)
    for k, v in st.items(): w(os.path.join("stem", f"{k}.wav"), v*g)
    print("raw audio", round(n/SR, 2), "s; mix", round(m.integrated_loudness(mixl), 1), "LUFS")

if __name__ == "__main__":
    main()
