"""Seliu v9 raw — sharpness per frame (mean |Laplacian| of luma) at the centre and in a 4x4 grid, plotted over time,
plus the largest frame-to-frame jumps (a level pop or a blur switching off shows as a step).
usage: raw_sharpness.py VIDEO OUT.png OUT.json"""
import sys, json, numpy as np, cv2
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

def main():
    src, png, js = sys.argv[1:4]
    cap = cv2.VideoCapture(src); rows = []
    while True:
        ok, fr = cap.read()
        if not ok: break
        y = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY).astype(np.float32)/255
        lap = np.abs(cv2.Laplacian(y, cv2.CV_32F, ksize=3))
        H, W = y.shape
        cells = [float(lap[i*H//4:(i+1)*H//4, j*W//4:(j+1)*W//4].mean()) for i in range(4) for j in range(4)]
        centre = float(lap[3*H//8:5*H//8, 3*W//8:5*W//8].mean())
        rows.append([centre]+cells)
    a = np.array(rows); t = np.arange(len(a))/25-3.0
    # steps: frame-to-frame change against the local trend (median of the 8 neighbouring changes)
    la = np.log(np.maximum(a, 1e-5)); dl = np.abs(np.diff(la, axis=0))
    from scipy.ndimage import median_filter
    trend = median_filter(dl, size=(9, 1))
    excess = dl-trend
    worst = [{"t": round(float(t[i+1]), 2), "cell": ("centre" if c == 0 else f"r{(c-1)//4}c{(c-1)%4}"), "jump_pct": round(float(np.expm1(dl[i, c])*100), 1),
              "trend_pct": round(float(np.expm1(trend[i, c])*100), 1)} for i, c in zip(*np.unravel_index(np.argsort(-excess, axis=None)[:12], excess.shape))]
    fig, ax = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    for c in range(1, 17): ax[0].plot(t, a[:, c], lw=0.7, alpha=0.6)
    ax[0].plot(t, a[:, 0], "k", lw=1.8, label="centre"); ax[0].legend(); ax[0].set_ylabel("sharpness (mean |Laplacian|)")
    ax[0].set_title("Seliu v9 raw — sharpness per frame: centre (black) and 4x4 grid")
    ax[1].plot(t[1:], dl[:, 0]*100, "k", lw=1.2, label="centre"); ax[1].plot(t[1:], dl[:, 1:].max(1)*100, color="tab:red", lw=0.8, label="max over grid")
    ax[1].set_ylabel("frame-to-frame change (%)"); ax[1].set_xlabel("time (s), 0 = old first frame"); ax[1].legend()
    for x in ax: x.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(png, dpi=110)
    json.dump({"frames": len(a), "largest_jumps_vs_trend": worst, "max_change_centre_pct": round(float(np.expm1(dl[:, 0].max())*100), 1)}, open(js, "w"), indent=1)
    print(json.dumps(worst[:5]))

if __name__ == "__main__":
    main()
