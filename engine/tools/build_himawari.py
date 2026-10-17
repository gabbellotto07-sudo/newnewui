"""Real clouds of the same moment for the orbit and the region: Himawari-8 AHI full disk,
29-07-2019 03:20 UTC (the Sentinel-2 hero overpass of Seliu), NOAA public bucket noaa-himawari8.
  opacity  = how white the scene is in the three visible bands (B01 blue, B02 green, B03 red, 1 km),
             above the clear surface
  top      = cloud-top height from the 10.4 um brightness temperature (B13, 2 km):
             h = (T_surface - T_top) / 6.5 K/km, clamped 0.6 .. 15 km
  parallax: a geostationary view at 140.7 E sees a cloud displaced away from the sub-satellite point
             by h * tan(view zenith); corrected before resampling.
usage: build_himawari.py LEVEL [LEVEL ...]  -> data/<LEVEL>_hcloud.npy (float16 opacity), data/<LEVEL>_htop.npy (m)"""
import sys, os, glob, numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geo import LEVELS
from render import aeqd
import warnings; warnings.filterwarnings("ignore")
from satpy import Scene

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
files = sorted(glob.glob(os.path.join(ROOT, "data", "himawari", "HS_H08_20190729_0320_*.DAT")))
scn = Scene(reader="ahi_hsd", filenames=files)
scn.load(["B01", "B02", "B03", "B13"])
lon, lat = scn["B03"].attrs["area"].get_lonlats()
b = [np.asarray(scn[k].values, np.float32)/100.0 for k in ("B01", "B02", "B03")]   # % -> reflectance (TOA)
lon13, lat13 = scn["B13"].attrs["area"].get_lonlats()
t13 = np.asarray(scn["B13"].values, np.float32)
t13 = cv2.resize(t13, (b[0].shape[1], b[0].shape[0]), interpolation=cv2.INTER_LINEAR)
# keep the Sundaland window only (memory)
win = (lon > 72) & (lon < 135) & (lat > -35) & (lat < 22)          # v9: wider (the 9:16 orbit saw the cut)
rows = np.nonzero(win.any(1))[0]; cols = np.nonzero(win.any(0))[0]
r0, r1, c0, c1 = rows[0], rows[-1]+1, cols[0], cols[-1]+1
lon, lat = lon[r0:r1, c0:c1], lat[r0:r1, c0:c1]; b = [x[r0:r1, c0:c1] for x in b]; t13 = t13[r0:r1, c0:c1]
ok = np.isfinite(lon) & np.isfinite(b[2])
wmin = np.minimum(np.minimum(b[0], b[1]), b[2])
# solar zenith at 03:20 UTC: TOA reflectance is already normalised by satpy; opacity from whiteness
white = np.clip((wmin-0.13)/0.35, 0, 1)
tsurf = float(np.nanpercentile(t13[np.isfinite(t13) & (wmin < 0.08)], 75))
cold = np.clip((tsurf-t13-2.5)/6.0, 0, 1)                 # a cloud is colder than the surface under it
op = white*cold; op = op*op*(3-2*op)
op = np.where(ok, op, 0).astype(np.float32)
# v9: near Himawari's own limb (view zenith > ~62 deg, west of ~80 E here) its pixels are stretched into streaks:
# those clouds are removed (soft), never replaced
_la, _lo = np.radians(np.where(ok, lat, 0)), np.radians(np.where(ok, lon, 0))
_n = np.stack([np.cos(_la)*np.cos(_lo), np.cos(_la)*np.sin(_lo), np.sin(_la)], -1)
_s = np.array([np.cos(np.radians(140.7)), np.sin(np.radians(140.7)), 0.0])*42164.0e3
_v = _s-_n*6371.0e3; _v /= np.linalg.norm(_v, axis=-1, keepdims=True)
vza = np.degrees(np.arccos(np.clip((_n*_v).sum(-1), -1, 1))); del _la, _lo, _n, _v
op *= np.clip((66.0-vza)/8.0, 0, 1).astype(np.float32)
# v9: the cloud's own measured brightness (TOA reflectance, mean of the three visible bands), same instant and sun
bright = np.where(ok, (b[0]+b[1]+b[2])/3, 0).astype(np.float32)
print("surface 10.4 um temperature", round(tsurf, 1), "K")
top = np.clip((tsurf-t13)/6.5, 0.6, 15.0)*1000.0
top = np.where(op > 0.02, top, 0).astype(np.float32)
# parallax correction (exact): the satellite S sees the cloud C on the line S -> P_obs, where P_obs is the
# geolocated surface point; C is where that line is at height h. Its true ground position is C projected down.
SAT_LON = 140.7; Rg = 42164.0e3; Re = 6371.0e3
def ecef(la, lo, r):
    la, lo = np.radians(la), np.radians(lo)
    return np.stack([r*np.cos(la)*np.cos(lo), r*np.cos(la)*np.sin(lo), r*np.sin(la)], -1)
S = ecef(np.array(0.0), np.array(SAT_LON), Rg)
P = ecef(np.where(ok, lat, 0), np.where(ok, lon, 0), Re)
dv = P-S; dv /= np.linalg.norm(dv, axis=-1, keepdims=True)
bq = (dv*S).sum(-1); cq = S@S-(Re+top)**2
tq = -bq-np.sqrt(np.maximum(bq*bq-cq, 0))
C = S+dv*tq[..., None]
lat_c = np.degrees(np.arcsin(np.clip(C[..., 2]/np.linalg.norm(C, axis=-1), -1, 1)))
lon_c = np.degrees(np.arctan2(C[..., 1], C[..., 0]))
del P, dv, C
for lvl in sys.argv[1:]:
    half, px = dict((n, (h, p)) for n, h, p in LEVELS)[lvl]; n = int(2*half/px)
    x, y = aeqd(lat_c[ok], lon_c[ok])
    col = ((x+half)/px-0.5); row = ((half-y)/px-0.5)
    inside = (col >= 0) & (col < n-1) & (row >= 0) & (row < n-1)
    ci, ri = np.round(col[inside]).astype(np.int64), np.round(row[inside]).astype(np.int64)
    acc = np.zeros(n*n, np.float64); cnt = np.zeros(n*n, np.float64); hac = np.zeros(n*n, np.float64)
    idx = ri*n+ci
    np.add.at(acc, idx, op[ok][inside]); np.add.at(hac, idx, top[ok][inside]*op[ok][inside]); np.add.at(cnt, idx, 1)
    bac = np.zeros(n*n, np.float64); np.add.at(bac, idx, bright[ok][inside]*op[ok][inside])
    acc = acc.reshape(n, n); cnt = cnt.reshape(n, n); hac = hac.reshape(n, n); bac = bac.reshape(n, n)
    valid = cnt > 0
    A = np.where(valid, acc/np.maximum(cnt, 1), 0).astype(np.float32); Ht = np.where(acc > 0, hac/np.maximum(acc, 1e-6), 0).astype(np.float32)
    # fill the holes left by forward mapping (grid finer than the source) with a normalised blur
    k = max(1.0, 1500.0/px)
    wv = cv2.GaussianBlur(valid.astype(np.float32), (0, 0), k)
    A2 = cv2.GaussianBlur(A*valid, (0, 0), k)/np.maximum(wv, 1e-4)
    H2 = cv2.GaussianBlur(Ht*A*valid, (0, 0), k)/np.maximum(cv2.GaussianBlur(A*valid, (0, 0), k), 1e-4)
    Bt = np.where(acc > 0, bac/np.maximum(acc, 1e-6), 0).astype(np.float32)
    B2 = cv2.GaussianBlur(Bt*A*valid, (0, 0), k)/np.maximum(cv2.GaussianBlur(A*valid, (0, 0), k), 1e-4)
    A = np.where(valid, A, A2); Ht = np.where(acc > 0, Ht, H2); Bt = np.where(acc > 0, Bt, B2)
    np.save(os.path.join(ROOT, "data", f"{lvl}_hbright.npy"), Bt.astype(np.float16))
    np.save(os.path.join(ROOT, "data", f"{lvl}_hcloud.npy"), np.clip(A, 0, 1).astype(np.float16))
    np.save(os.path.join(ROOT, "data", f"{lvl}_htop.npy"), Ht.astype(np.float32))
    cv2.imwrite(os.path.join(ROOT, "review", f"{lvl}_hcloud.jpg"), (np.clip(A[::2, ::2], 0, 1)*255).astype(np.uint8))
    print(lvl, "cloud cover >0.3", float((A > 0.3).mean()), "median top (m)", float(np.median(Ht[A > 0.3])) if (A > 0.3).any() else 0)
