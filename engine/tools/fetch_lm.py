"""Sentinel-2 L2A for the Belitung level LM (+-90 km around Seliu, 15 m) from the AWS COGs.
All MGRS tiles of one acquisition date are warped into one AEQD grid (UTM 48 and 49 both).
usage: fetch_lm.py YYYYMMDD [SAT]   -> data/LM_<date>.npy  uint16 (R, G, B, SCL), 0 = no data
Tile list from the Element84 earth-search STAC catalogue (sentinel-2-l2a)."""
import sys, os, json, urllib.request, numpy as np, rasterio, concurrent.futures as cf
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import transform_bounds
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from geo import AEQD, LEVELS
lvl = "LM"; half, px = dict((n, (h, p)) for n, h, p in LEVELS)[lvl]; n = int(2*half/px)
tr = from_origin(-half, half, px, px)
date = sys.argv[1]; sat = sys.argv[2] if len(sys.argv) > 2 else None
W, S, E, N = transform_bounds(AEQD, "EPSG:4326", -half, -half, half, half, densify_pts=50)
d = f"{date[:4]}-{date[4:6]}-{date[6:]}"
body = {"collections": ["sentinel-2-l2a"], "bbox": [W, S, E, N], "datetime": f"{d}T00:00:00Z/{d}T23:59:59Z", "limit": 50}
r = json.load(urllib.request.urlopen(urllib.request.Request("https://earth-search.aws.element84.com/v1/search",
        json.dumps(body).encode(), {"Content-Type": "application/json"})))
items = [f for f in r["features"] if sat is None or f["id"].startswith(sat)]
# one processing baseline per tile (drop duplicate _1 reprocessings when _0 exists)
seen = {}
for f in sorted(items, key=lambda f: f["id"]):
    seen.setdefault(f["id"].split("_")[1], f)
items = list(seen.values())
print(date, [f["id"] for f in items], flush=True)
out = np.zeros((4, n, n), np.uint16)
def warp(job):
    href, band = job
    rs = Resampling.nearest if band == 3 else Resampling.cubic
    with rasterio.open(href) as ds, WarpedVRT(ds, crs=AEQD, transform=tr, width=n, height=n, resampling=rs, nodata=0) as v:
        return band, v.read(1)
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
with cf.ThreadPoolExecutor(4) as ex:
    for f in items:                                 # tile by tile: the first tile with data wins on overlaps
        a = f["assets"]
        bands = dict(ex.map(warp, [(a[k]["href"], b) for b, k in enumerate(["red", "green", "blue", "scl"])]))
        m = (bands[3] > 0) & (out[3] == 0)
        for b in range(4): out[b][m] = bands[b][m]
        off = f["properties"].get("earthsearch:boa_offset_applied")
        print(" ", f["id"], "pixels", int(m.sum()), "boa_offset_applied", off, flush=True)
np.save(f"data/LM_{date}.npy", out); print(date, "valid", float((out[3] > 0).mean()), flush=True)
