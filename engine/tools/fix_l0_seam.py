"""v9: the L0 mosaic has a brighter band (~6 %) at columns 1774-1781 (x ~ -278 km, southern Sumatra), seen as a
straight line at 6.8-8.3 s. Divide it out: per row, the ratio of each band column to the line joining the clean
columns on both sides, measured on land only and smoothed along the rows; applied as a gain (rgb).
Idempotent via a marker file."""
import os, sys, numpy as np, cv2
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(ROOT, "data", "L0_tex.npy"); mark = p+".seamfix"
if os.path.exists(mark): sys.exit("already fixed")
a = np.load(p, mmap_mode="r+")
X0 = 1760
rgb = np.array(a[:3, :, X0:1796], np.float32); land = np.array(a[3, :, X0:1796]) > 0.5
lum = rgb.mean(0)
lc, rc = [1769, 1770, 1771, 1772], [1784, 1785, 1786, 1787]
left = lum[:, [c-X0 for c in lc]].mean(1); right = lum[:, [c-X0 for c in rc]].mean(1)
ok_lr = land[:, [c-X0 for c in lc+rc]].all(1)
def nblur(v, m, s=30):
    num = cv2.GaussianBlur((v*m).astype(np.float32)[:, None], (1, 0), s).ravel()
    den = cv2.GaussianBlur(m.astype(np.float32)[:, None], (1, 0), s).ravel()
    return num/np.maximum(den, 1e-4), den
for c in range(1773, 1784):
    w = (c-1771.5)/(1785.5-1771.5)
    ref = left*(1-w)+right*w
    m = (ok_lr & land[:, c-X0]).astype(np.float32)
    ratio, den = nblur(np.log(np.maximum(lum[:, c-X0], 1e-4)/np.maximum(ref, 1e-4)), m)
    g = np.exp(-np.clip(ratio, -0.15, 0.15)*np.clip(den/0.2, 0, 1))
    rgb[:, :, c-X0] *= g[None]
a[:3, :, X0:1796] = rgb; a.flush(); open(mark, "w").write("done\n")
print("fixed")
