"""Copernicus DEM GLO-30 (AWS public bucket copernicus-dem-30m) -> AEQD grid of a level.
Land relief at 30 m (DSM: includes canopy height). Sea pixels are 0 in the product.
usage: fetch_cop.py LEVEL -> data/<LEVEL>_cop.npy (float32 metres)"""
import sys, math, numpy as np, rasterio
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import transform_bounds
sys.path.insert(0, __file__.rsplit('/', 1)[0]); from geo import AEQD, LEVELS
B = "https://copernicus-dem-30m.s3.amazonaws.com/"
lvl = sys.argv[1]; half, px = dict((n, (h, p)) for n, h, p in LEVELS)[lvl]; n = int(2*half/px)
tr = from_origin(-half, half, px, px)
W, S, E, N = transform_bounds(AEQD, "EPSG:4326", -half, -half, half, half, densify_pts=50)
out = np.zeros((n, n), np.float32); have = np.zeros((n, n), bool)
for lat in range(math.floor(S), math.ceil(N)):
    for lon in range(math.floor(W), math.ceil(E)):
        ns = ("N" if lat >= 0 else "S")+f"{abs(lat):02d}"; ew = ("E" if lon >= 0 else "W")+f"{abs(lon):03d}"
        name = f"Copernicus_DSM_COG_10_{ns}_00_{ew}_00_DEM"
        try:
            with rasterio.open(f"/vsicurl/{B}{name}/{name}.tif") as ds, WarpedVRT(ds, crs=AEQD, transform=tr, width=n, height=n,
                    resampling=Resampling.cubic if px < 30 else Resampling.average, nodata=-9999) as v:
                a = v.read(1); m = a > -9000
                out[m] = a[m]; have |= m; print(name, m.mean(), flush=True)
        except Exception as e:
            print("missing", name, type(e).__name__, flush=True)   # all-sea tiles do not exist
np.save(f"data/{lvl}_cop.npy", out); print(lvl, "relief", float(out.min()), float(out.max()), "covered", float(have.mean()))
