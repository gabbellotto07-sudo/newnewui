"""Seliu coastline for the drawn outline -> data/seliu_outline_lonlat.json

Source: land mask of the L2 level (channel 3 of data/L2_comp.npy, Sentinel-2 10 m, land Aug 2026).
Seliu = connected land component containing (row 3250, col 3090), same rule as make_light.py.
Steps: crop -> component -> fill holes -> light morphological smoothing -> outer contour (sub-pixel via
upsampled blurred mask) -> periodic Gaussian smoothing (~25 m) -> uniform resampling (~12 m) ->
rotate so the polyline starts at the coast point nearest the Pulau Seliu village jetty, ordered
counter-clockwise on the map. Points are lon/lat (WGS84).
"""
import os, sys, json, numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geo import lonlat, xy, PLACES
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
a = np.load(os.path.join(ROOT, "data", "L2_comp.npy"), mmap_mode="r")
R0, R1, C0, C1 = 2500, 4100, 2300, 3900                  # 16 x 16 km window around Seliu
land = (np.array(a[3, R0:R1, C0:C1]) > 0.5).astype(np.uint8)
n, lab = cv2.connectedComponents(land, connectivity=8)
isl = (lab == lab[3250-R0, 3090-C0]).astype(np.uint8)
assert isl.sum() > 1000, "Seliu component not found"
# fill interior holes (lagoons / misclassified clearings are not coastline)
cnts, _ = cv2.findContours(isl, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
fill = np.zeros_like(isl); cv2.drawContours(fill, cnts, -1, 1, -1)
# sub-pixel contour: upsample x4 a blurred mask (sigma 1.5 px = 15 m) and take the 0.5 level
U = 4
m = cv2.GaussianBlur(fill.astype(np.float32), (0, 0), 1.5)
mu = cv2.resize(m, (m.shape[1]*U, m.shape[0]*U), interpolation=cv2.INTER_CUBIC)
cnts, _ = cv2.findContours((mu > 0.5).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
c = max(cnts, key=cv2.contourArea)[:, 0, :].astype(np.float64)
col = C0+(c[:, 0]+0.5)/U-0.5; row = R0+(c[:, 1]+0.5)/U-0.5
X = -32000+(col+0.5)*10; Y = 32000-(row+0.5)*10
# periodic Gaussian smoothing along arc length, then uniform resampling
def resample(X, Y, step):
    d = np.hypot(np.diff(np.r_[X, X[0]]), np.diff(np.r_[Y, Y[0]])); s = np.r_[0, np.cumsum(d)]
    L = s[-1]; n = int(L/step); u = np.linspace(0, L, n, endpoint=False)
    return np.interp(u, s, np.r_[X, X[0]]), np.interp(u, s, np.r_[Y, Y[0]]), L
X, Y, L = resample(X, Y, 2.5)
sig = 25.0/2.5; k = np.arange(-int(4*sig), int(4*sig)+1); g = np.exp(-0.5*(k/sig)**2); g /= g.sum()
wrap = lambda v: np.convolve(np.r_[v[-len(k):], v, v[:len(k)]], g, "same")[len(k):-len(k)]
X, Y = wrap(X), wrap(Y)
X, Y, L = resample(X, Y, 12.0)
# orientation: counter-clockwise (positive signed area in x-east / y-north)
area = 0.5*np.sum(X*np.roll(Y, -1)-np.roll(X, -1)*Y)
if area < 0: X, Y = X[::-1], Y[::-1]
jx, jy = xy(*PLACES["seliu_landing"])
i0 = int(np.argmin(np.hypot(X-jx, Y-jy)))
X, Y = np.roll(X, -i0), np.roll(Y, -i0)
lo, la = lonlat(X, Y)
out = {"source": "data/L2_comp.npy channel 3 (land mask >0.5), Sentinel-2 10 m, land Aug 2026",
       "component_seed_rowcol": [3250, 3090], "smoothing_m": 25, "spacing_m": 12,
       "start": "coast point nearest Pulau Seliu village jetty (107.5449, -3.1994)", "orientation": "counter-clockwise",
       "perimeter_m": round(float(L), 1), "area_km2": round(float(abs(area))/1e6, 3),
       "start_offset_from_jetty_m": round(float(np.hypot(X[0]-jx, Y[0]-jy)), 1),
       "lonlat": [[round(float(o), 6), round(float(t), 6)] for o, t in zip(lo, la)]}
json.dump(out, open(os.path.join(ROOT, "data", "seliu_outline_lonlat.json"), "w"))
print({k: v for k, v in out.items() if k != "lonlat"}, len(out["lonlat"]), "points")
