"""ESA WorldCover 2021 Sentinel-2 RGBNIR cloud-free annual composite -> AEQD grid of a level.
Land only (the sea far from coasts is not in the product).  -> data/<LEVEL>_esa.npy float32 R,G,B,NIR,valid"""
import sys, re, urllib.request, numpy as np, rasterio, concurrent.futures as cf
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import transform_bounds
sys.path.insert(0, __file__.rsplit('/',1)[0]); from geo import AEQD, LEVELS
lvl=sys.argv[1]; half,px=dict((n,(h,p)) for n,h,p in LEVELS)[lvl]; n=int(2*half/px); tr=from_origin(-half,half,px,px)
W,S,E,N=transform_bounds(AEQD,"EPSG:4326",-half,-half,half,half,densify_pts=50)
BU="https://esa-worldcover-s2.s3.eu-central-1.amazonaws.com/"
keys=[]
for lat in range(int(np.floor(S)),int(np.ceil(N))):
    tag=("N" if lat>=0 else "S")+f"{abs(lat):02d}"
    x=urllib.request.urlopen(BU+f"?list-type=2&prefix=rgbnir/2021/{tag}/").read().decode()
    for k in re.findall(r"<Key>([^<]*)</Key>",x):
        lon=int(re.search(r"_[NS]\d\d([EW])(\d{3})_",k).group(2))*(1 if re.search(r"_[NS]\d\d([EW])",k).group(1)=="E" else -1)
        if W-1<=lon<=E: keys.append(k)
print(len(keys),"tiles",flush=True)
OVR = 3 if px >= 400 else (2 if px >= 150 else None)   # read a coarse overview for wide levels
def one(k):
    kw = {"overview_level": OVR} if OVR is not None else {}
    with rasterio.open("/vsicurl/"+BU+k, **kw) as ds, WarpedVRT(ds,crs=AEQD,transform=tr,width=n,height=n,
            resampling=Resampling.average if px>=50 else Resampling.cubic,nodata=0) as v:
        win=v.window(*rasterio.coords.BoundingBox(*transform_bounds(ds.crs,AEQD,*ds.bounds,densify_pts=21)))
        try: win=win.round_offsets().round_lengths().intersection(rasterio.windows.Window(0,0,n,n))
        except Exception: return None, None
        return win, v.read(window=win)
acc=np.zeros((5,n,n),np.float32)
with cf.ThreadPoolExecutor(8) as ex:
    for win,a in ex.map(one,keys):
        if win is None: continue
        r0,c0=int(win.row_off),int(win.col_off); h,w=a.shape[1:]
        m=a[0]>0; sl=(slice(r0,r0+h),slice(c0,c0+w))
        for i in range(4): acc[i][sl][m]=a[i][m]/10000.0
        acc[4][sl][m]=1
np.save(f"data/{lvl}_esa.npy",acc); print("valid",acc[4].mean())
