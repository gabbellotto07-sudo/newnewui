"""Shared geography for Seliu v5. All positions WGS84 lon/lat; working CRS is an
azimuthal equidistant projection centred on Seliu so the whole descent lives in
one metric plane (no Mercator stretch)."""
from pyproj import CRS, Transformer
LON0, LAT0 = 107.532, -3.215                    # Seliu centre
AEQD = CRS.from_proj4(f"+proj=aeqd +lat_0={LAT0} +lon_0={LON0} +datum=WGS84 +units=m")
_fwd = Transformer.from_crs(4326, AEQD, always_xy=True)
_inv = Transformer.from_crs(AEQD, 4326, always_xy=True)
def xy(lon, lat): return _fwd.transform(lon, lat)
def lonlat(x, y): return _inv.transform(x, y)

# Places (verified; see docs/fonti.md)
PLACES = {
    "singapore":    (103.8198, 1.3521),   # city centre
    "jakarta":      (106.8456, -6.2088),  # city centre
    "tjq":          (107.7546, -2.7455),  # H.A.S. Hanandjoeddin airport, Tanjung Pandan (not labelled)
    "teluk_gembira_pier": (107.5857, -3.1973),  # jetty at headland tip, read on S2 2019-07-29 + 2026-08-08
    "seliu_landing": (107.5449, -3.1994),  # village jetty, Desa Pulau Seliu, north-east shore (S2 10 m)
    "seliu_label": (107.522, -3.222),     # visual centre of the island
    "seliu_south_tip": (107.519, -3.256),
    "changi": (103.9915, 1.3644), "cgk": (106.6559, -6.1256),
    "belitung_centre": (107.93, -2.86),
    "seliu":        (LON0, LAT0),
}
# Pyramid levels: name, half-extent (m), pixel size (m)
LEVELS = [
    ("LG", 3_600_000, 1800),
    ("L0", 1_700_000, 800),
    ("L1",   230_000, 100),
    ("LM",    90_000,  15),     # v8: all of Belitung + the western cloud field at Sentinel-2 detail
    ("L2",    32_000,  10),
]
