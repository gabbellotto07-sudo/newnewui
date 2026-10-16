"""Export the four map plates (graded like the film, no haze/vignette/text) + layers + georeference.
Each plate is an azimuthal-equidistant image centred on Seliu: pixel (col,row) -> metres x = -half+(col+.5)*px,
y = half-(row+.5)*px -> lon/lat with the projection in plates.json. Anchor pixel positions are precomputed."""
import sys, os, json, numpy as np, cv2
sys.path.insert(0, os.path.dirname(__file__))
from geo import LEVELS, PLACES, LON0, LAT0, xy
import render as R
OUT = "delivery/raw/plates"; os.makedirs(OUT, exist_ok=True)
meta = {"projection": f"+proj=aeqd +lat_0={LAT0} +lon_0={LON0} +datum=WGS84 +units=m",
        "pixel_to_metres": "x = -half_m + (col + 0.5) * px_m ; y = half_m - (row + 0.5) * px_m",
        "plates": {}}
desc = {"LG": "Continent (±3600 km): ESA WorldCover 2021 S2 mosaic + bathymetry-coloured sea",
        "L0": "Region (±1700 km): Singapore, Jakarta, Sumatra, Borneo, Java",
        "L1": "Belitung (±230 km): land ESA 2021, Belitung shelf water Sentinel-2 29-07-2019",
        "L2": "Seliu (±32 km, 10 m/px): sea Sentinel-2 29-07-2019 (cloud-cleaned), land Sentinel-2 Aug 2026"}
look = dict(R.LOOK)
for name, half, px in LEVELS:
    p = "data/L2_comp.npy" if name == "L2" else f"data/{name}_tex.npy"
    A = np.load(p, mmap_mode="r"); n = A.shape[1]
    img16 = np.zeros((n, n, 3), np.uint16)
    for r0 in range(0, n, 512):
        strip = np.ascontiguousarray(np.array(A[:3, r0:r0+512]).transpose(1, 2, 0), np.float32)
        g = R.grade(strip, look)
        img16[r0:r0+512] = (np.clip(g, 0, 1)*65535+0.5).astype(np.uint16)
    cv2.imwrite(f"{OUT}/{name}_color_16bit.png", cv2.cvtColor(img16, cv2.COLOR_RGB2BGR))
    prev = cv2.resize((img16 >> 8).astype(np.uint8), (min(n, 4096),)*2, interpolation=cv2.INTER_AREA)
    cv2.imwrite(f"{OUT}/{name}_color_preview.jpg", cv2.cvtColor(prev, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 92])
    cv2.imwrite(f"{OUT}/{name}_land_mask.png", ((np.array(A[3]) > 0.5)*255).astype(np.uint8))
    layers = {"color_16bit": f"{name}_color_16bit.png", "preview": f"{name}_color_preview.jpg", "land_mask": f"{name}_land_mask.png"}
    if os.path.exists(f"data/{name}_clouds.npy"):
        c = np.load(f"data/{name}_clouds.npy").astype(np.float32)
        cv2.imwrite(f"{OUT}/{name}_clouds_alpha_16bit.png", (np.clip(c, 0, 1)*65535).astype(np.uint16)); layers["clouds_alpha"] = f"{name}_clouds_alpha_16bit.png"
    if name == "L2":
        m = np.load("data/L2_light.npy"); cv2.imwrite(f"{OUT}/L2_seliu_light_matte_16bit.png", (np.clip(m, 0, 1)*65535).astype(np.uint16)); layers["seliu_light_matte"] = "L2_seliu_light_matte_16bit.png"
    anchors = {}
    for k, (lo, la) in PLACES.items():
        X, Y = xy(lo, la); col = (X+half)/px-0.5; row = (half-Y)/px-0.5
        if 0 <= col < n and 0 <= row < n: anchors[k] = [round(col, 1), round(row, 1)]
    meta["plates"][name] = {"description": desc[name], "size_px": n, "half_m": half, "px_m": px, "layers": layers, "anchors_px": anchors}
    print(name, n, "done", flush=True)
meta["clouds_note"] = "Real clouds of 29-07-2019 lifted off the ground: put them ~850 m above the sea; their shadows fall to the SW (sun azimuth 47 deg, elevation 57 deg): offset ~550 m toward azimuth 227 deg."
json.dump(meta, open(f"{OUT}/plates.json", "w"), indent=1)
