"""v9: LM water (median of the clear 2026 passes, 15 m) keeps its detail, but its large-scale tone (> ~8 km)
is matched to the hero scene of 29-07-2019 as it is in L1 before any injection (data/L1_own.npy). This removes
the step at the LM/L1 border and most of the faint Sentinel-2 tile seams of the 2026 median, and makes the sea
of the descent the same day as the sea around Seliu. Land is untouched. Run once, then re-inject LM->L1->L0->LG.
usage: harmonize_lm_water.py   (reads data/LM_tex.npy, data/L1_own.npy; writes data/LM_tex.npy in place)"""
import sys, os, numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geo import LEVELS
L = dict((a, (b, c)) for a, b, c in LEVELS)
hM, pM = L["LM"]; h1, p1 = L["L1"]
M = np.load("data/LM_tex.npy", mmap_mode="r+"); n = M.shape[1]
O = np.load("data/L1_own.npy", mmap_mode="r")
F = 16                                            # work grid: 240 m
m = n//F
land = cv2.resize(np.array(M[3], np.float32), (m, m), interpolation=cv2.INTER_AREA)
water = (land < 0.02).astype(np.float32)
# L1 own pixels covering the LM grid at 240 m
xs = -hM+(np.arange(m)+0.5)*pM*F
ys = hM-(np.arange(m)+0.5)*pM*F
u = ((xs+h1)/p1-0.5).astype(np.float32); v = ((h1-ys)/p1-0.5).astype(np.float32)
U, V = np.meshgrid(u, v)
SIG = 8000/(pM*F)                                 # 8 km

def lowpass(a, w):
    return cv2.GaussianBlur(a*w, (0, 0), SIG)/np.maximum(cv2.GaussianBlur(w, (0, 0), SIG), 1e-4)

olw = cv2.remap((np.array(O[3]) < 0.5).astype(np.float32), U, V, cv2.INTER_LINEAR)
wv = water*(olw > 0.98)
for c in range(3):
    lm = cv2.resize(np.array(M[c], np.float32), (m, m), interpolation=cv2.INTER_AREA)
    ow = cv2.remap(np.array(O[c], np.float32), U, V, cv2.INTER_LINEAR)
    ratio = lowpass(ow, wv)/np.maximum(lowpass(lm, wv), 1e-4)
    ratio = np.clip(ratio, 0.6, 1.6)
    R = cv2.resize(ratio, (n, n), interpolation=cv2.INTER_CUBIC)
    wl = 1-np.clip(cv2.resize(cv2.GaussianBlur(land, (0, 0), 1.0), (n, n), interpolation=cv2.INTER_LINEAR)*4, 0, 1)
    for r0 in range(0, n, 1000):                 # in row blocks (memory)
        sl = slice(r0, min(n, r0+1000))
        k = 1+(R[sl]-1)*wl[sl]
        M[c, sl] = np.array(M[c, sl])*k
    print("channel", c, "ratio range", float(ratio[wv > 0].min()), float(ratio[wv > 0].max()), flush=True)
M.flush()
v = np.clip(np.stack([np.array(M[c, ::8, ::8]) for c in range(3)], -1)*3.0, 0, 1)**(1/2.2)
cv2.imwrite("review/LM_tex.jpg", cv2.cvtColor((v*255).astype(np.uint8), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 88])
print("done")
