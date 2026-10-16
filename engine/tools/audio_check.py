"""Audio checks required before every delivery:
  integrated loudness, LRA (ffmpeg ebur128), true peak, band energy, loudness per second,
  mono compatibility (L/R correlation, mono vs stereo loudness), phone speaker simulation
  (high-pass ~300 Hz + low-pass 8 kHz: the story must survive), spectrogram image.
usage: audio_check.py MIX.wav OUTPREFIX"""
import sys, subprocess, json, re, numpy as np, soundfile as sf, pyloudnorm as pyln
from scipy import signal
import cv2

def ebur(path):
    r = subprocess.run(["ffmpeg", "-nostats", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    s = r[r.rfind("Summary"):]
    g = lambda k: float(re.search(k+r":\s+(-?[\d.]+)", s).group(1))
    return dict(I=g("I"), LRA=g("LRA"), TP=g("Peak"))

def main(path, prefix):
    x, sr = sf.read(path, always_2d=True); m = x.mean(1)
    meter = pyln.Meter(sr)
    out = ebur(path)
    X = np.abs(np.fft.rfft(m))**2; f = np.fft.rfftfreq(len(m), 1/sr); T = X.sum()
    out["bands_pct"] = {f"{a}-{b}": round(100*X[(f >= a) & (f < b)].sum()/T, 1) for a, b in ((0, 200), (200, 2000), (2000, 8000), (8000, 24000))}
    out["LR_correlation"] = round(float(np.corrcoef(x[:, 0], x[:, 1])[0, 1]), 3)
    mono = np.stack([m, m], 1)
    out["mono_minus_stereo_LU"] = round(meter.integrated_loudness(mono)-meter.integrated_loudness(x), 2)
    ph = signal.sosfilt(signal.butter(4, [300, 8000], "bandpass", fs=sr, output="sos"), m)
    out["phone_minus_full_LU"] = round(meter.integrated_loudness(np.stack([ph, ph], 1))-meter.integrated_loudness(x), 2)
    # short-term loudness each 0.5 s, full and phone
    w = int(0.4*sr); hop = int(0.5*sr)
    def st(sig):
        r = []
        for i in range(0, len(sig)-w, hop):
            seg = sig[i:i+w]; r.append(round(10*np.log10(np.mean(seg**2)+1e-12), 1))
        return r
    out["rms_db_every_0.5s"] = st(m); out["phone_rms_db_every_0.5s"] = st(ph)
    json.dump(out, open(prefix+"_check.json", "w"), indent=1)
    # spectrogram (log frequency), with the phone band marked
    fs, ts, S = signal.spectrogram(m, sr, nperseg=4096, noverlap=3072)
    S = 10*np.log10(S+1e-14)
    lf = np.geomspace(30, 20000, 400)
    img = np.stack([np.interp(lf, fs, S[:, j]) for j in range(S.shape[1])], 1)[::-1]
    v = np.clip((img-img.max()+90)/90, 0, 1)
    v = cv2.resize((v*255).astype(np.uint8), (1400, 400), interpolation=cv2.INTER_LINEAR)
    v = cv2.applyColorMap(v, cv2.COLORMAP_MAGMA)
    for fr, lab in ((100, "100"), (300, "300"), (1000, "1k"), (2000, "2k"), (8000, "8k")):
        yy = int(400-np.log(fr/30)/np.log(20000/30)*400); cv2.line(v, (0, yy), (1400, yy), (90, 90, 90), 1)
        cv2.putText(v, lab, (4, yy-3), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
    dur = len(m)/sr
    for s_ in range(0, int(dur)+1, 2):
        xx = int(s_/dur*1400); cv2.line(v, (xx, 390), (xx, 400), (200, 200, 200), 1); cv2.putText(v, str(s_), (xx+2, 396), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (200, 200, 200), 1)
    cv2.imwrite(prefix+"_spectrogram.png", v)
    print(json.dumps({k: v for k, v in out.items() if "every" not in k}, indent=1))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
