"""AWS terrain tiles (terrarium; land from SRTM etc, sea floor from GEBCO/ETOPO) -> AEQD grid. -> data/<LEVEL>_dem.npy (m)"""
import sys, io, math, urllib.request, numpy as np, concurrent.futures as cf
from PIL import Image
import rasterio
from rasterio.warp import reproject, Resampling, transform_bounds
from rasterio.transform import from_origin, from_bounds
sys.path.insert(0, __file__.rsplit('/',1)[0]); from geo import AEQD, LEVELS
lvl=sys.argv[1]; z=int(sys.argv[2]); half,px=dict((n,(h,p)) for n,h,p in LEVELS)[lvl]; n=int(2*half/px)
W,S,E,N=transform_bounds(AEQD,"EPSG:4326",-half,-half,half,half,densify_pts=50)
def tx(lon): return int((lon+180)/360*2**z)
def ty(lat): r=math.radians(lat); return int((1-math.log(math.tan(r)+1/math.cos(r))/math.pi)/2*2**z)
xs=range(tx(W),tx(E)+1); ys=range(ty(N),ty(S)+1)
def get(t):
    x,y=t; d=urllib.request.urlopen(f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png").read()
    a=np.asarray(Image.open(io.BytesIO(d)).convert("RGB")).astype(np.float32)
    return t,a[...,0]*256+a[...,1]+a[...,2]/256-32768
big=np.zeros((len(ys)*256,len(xs)*256),np.float32)
with cf.ThreadPoolExecutor(16) as ex:
    for (x,y),a in ex.map(get,[(x,y) for y in ys for x in xs]):
        big[(y-ys[0])*256:(y-ys[0]+1)*256,(x-xs[0])*256:(x-xs[0]+1)*256]=a
R=6378137*math.pi; m=2*R/2**z
src_tr=from_origin(-R+xs[0]*m, R-ys[0]*m, m/256, m/256)
out=np.zeros((n,n),np.float32)
reproject(big,out,src_transform=src_tr,src_crs="EPSG:3857",dst_transform=from_origin(-half,half,px,px),dst_crs=AEQD,resampling=Resampling.cubic)
np.save(f"data/{lvl}_dem.npy",out); print(lvl,out.min(),out.max())
