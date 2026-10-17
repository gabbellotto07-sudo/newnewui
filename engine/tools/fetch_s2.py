"""Fetch one Sentinel-2 L2A scene (AWS sentinel-cogs) into the AEQD grid of a level.
usage: fetch_s2.py LEVEL SCENE_ID -> data/<LEVEL>_<SCENE>.npy  (uint16 R,G,B,SCL)"""
import sys, numpy as np, rasterio
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
from rasterio.transform import from_origin
sys.path.insert(0, __file__.rsplit('/',1)[0]); from geo import AEQD, LEVELS
B="https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/"
lvl,sid=sys.argv[1],sys.argv[2]
half,px=dict((n,(h,p)) for n,h,p in LEVELS)[lvl]; n=int(2*half/px); tr=from_origin(-half,half,px,px)
t=sid.split('_')[1]; z,b,g=t[:2],t[2],t[3:]; d=sid.split('_')[2]
base=f"/vsicurl/{B}{z}/{b}/{g}/{int(d[:4])}/{int(d[4:6])}/{sid}/"
out=np.zeros((4,n,n),np.uint16)
for i,band in enumerate(["B04","B03","B02","SCL"]):
    with rasterio.open(base+band+".tif") as ds, WarpedVRT(ds,crs=AEQD,transform=tr,width=n,height=n,
            resampling=Resampling.nearest if band=="SCL" else (Resampling.cubic if px<=20 else Resampling.average),nodata=0) as v:
        out[i]=v.read(1)
np.save(f"data/{lvl}_{sid}.npy",out); print(sid,(out[3]>0).mean(),flush=True)
