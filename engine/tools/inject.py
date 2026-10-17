"""Pyramid consistency: write each finer level, downsampled, into the next coarser level with the
same edge feather the renderer uses. The coarse level then already contains what the fine level shows,
so switching level during the dive changes sharpness only, never colour.
usage: inject.py FINE COARSE"""
import sys, numpy as np, cv2
sys.path.insert(0, __file__.rsplit('/',1)[0]); from geo import LEVELS
FEATHER = 0.25
fine, coarse = sys.argv[1], sys.argv[2]
L = dict((a,(b,c)) for a,b,c in LEVELS); hf,pf = L[fine]; hc,pc = L[coarse]
fp = "data/L2_comp.npy" if fine=="L2" else f"data/{fine}_tex.npy"
F = np.load(fp, mmap_mode="r"); C = np.load(f"data/{coarse}_tex.npy")
nf = F.shape[1]; k = int(round(pc/pf))
small = np.stack([cv2.resize(np.array(F[i]), (nf//k, nf//k), interpolation=cv2.INTER_AREA) for i in range(4)])
m = small.shape[1]; c0 = int(round((hc-hf)/pc))
yy, xx = np.mgrid[0:m, 0:m].astype(np.float32)
e = np.maximum(np.abs((xx+.5)/m*2-1), np.abs((yy+.5)/m*2-1))
w = np.clip((1-e)/FEATHER, 0, 1)
if fine == 'L2':
    r = np.hypot((xx+.5)/m*2-1, (yy+.5)/m*2-1)*hf
    w = np.minimum(w, np.clip((30000-r)/14000, 0, 1))
sl = (slice(c0, c0+m), slice(c0, c0+m))
for i in range(3): C[i][sl] = C[i][sl]*(1-w)+small[i]*w
C[3][sl] = np.where(w > 0.5, small[3] > 0.5, C[3][sl])
np.save(f"data/{coarse}_tex.npy", C); print("injected", fine, "->", coarse, m, "px at", c0)
