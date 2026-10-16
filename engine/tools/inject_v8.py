"""Pyramid consistency (v8): write a finer level, filtered to the coarser pixel, into the coarser level
with the renderer's feather, so a level switch changes sharpness only, never colour or position.
Exact for any resolution ratio (v5 inject.py rounded 1800/800 to 2: the region was pasted 12.5 % too big
into LG). usage: inject_v8.py FINE COARSE"""
import sys, os, numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from geo import LEVELS
FILES = {"L2": "data/L2_comp.npy", "LM": "data/LM_tex.npy"}
fine, coarse = sys.argv[1], sys.argv[2]
L = dict((a, (b, c)) for a, b, c in LEVELS); hf, pf = L[fine]; hc, pc = L[coarse]
F = np.load(FILES.get(fine, f"data/{fine}_tex.npy"), mmap_mode="r")
C = np.load(f"data/{coarse}_tex.npy")
k = pc/pf
# window of the coarse grid that covers the fine level
c0 = int(np.floor((hc-hf)/pc))-1; side = int(np.ceil(2*hf/pc))+3
# coarse pixel j (in window) centre: x = -hc+(c0+j+.5)*pc  ->  fine pixel coordinate (x+hf)/pf-.5
off = ((-hc+(c0+0.5)*pc)+hf)/pf-0.5
# prefilter the fine level to the coarse footprint, then sample at the coarse pixel centres
small = []
for i in range(4):
    a = np.array(F[i], np.float32)
    if k > 1.5:
        f = int(np.floor(k))
        a = cv2.resize(a, (a.shape[1]//f, a.shape[0]//f), interpolation=cv2.INTER_AREA)   # box down by the integer part
        s = a.shape[1]/F.shape[2]
        M = np.array([[k*s, 0, (off+0.5)*s-0.5], [0, k*s, (off+0.5)*s-0.5]], np.float32)
        rem = k/f
        if rem > 1.05: a = cv2.GaussianBlur(a, (0, 0), 0.5*(rem-1)+0.3)
    else:
        M = np.array([[k, 0, off], [0, k, off]], np.float32)
    small.append(cv2.warpAffine(a, M, (side, side), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE))
small = np.stack(small)
yy, xx = np.mgrid[0:side, 0:side].astype(np.float32)
X = -hc+(c0+xx+.5)*pc; Y = hc-(c0+yy+.5)*pc
e = np.maximum(np.abs(X), np.abs(Y))/hf
w = np.clip((1-e)/0.25, 0, 1)
if fine == "L2": w = np.minimum(w, np.clip((30000-np.hypot(X, Y))/14000, 0, 1))
if fine == "LM": w = np.minimum(w, np.clip((88000-np.hypot(X, Y))/16000, 0, 1))
sl = (slice(c0, c0+side), slice(c0, c0+side))
for i in range(3): C[i][sl] = C[i][sl]*(1-w)+small[i]*w
C[3][sl] = np.where(w > 0.5, small[3] > 0.5, C[3][sl])
np.save(f"data/{coarse}_tex.npy", C); print("injected", fine, "->", coarse, "ratio", k, "window", c0, side)
