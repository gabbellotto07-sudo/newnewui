"""Assemble the texture of a wide level (L0/L1):
   land  = ESA WorldCover 2021 S2 cloud-free composite (colour-matched to the hero scene)
   water = hero Sentinel-2 scenes of 2019-07-29 where available (real water),
           elsewhere a depth-driven water colour learned from those same hero pixels
           (bathymetry: AWS terrain tiles / GEBCO), feather-blended.
usage: build_level.py LEVEL [HERO_SCENE...] -> data/<LEVEL>_tex.npy  (R,G,B reflectance, land)"""
import sys, json, os, numpy as np, cv2
lvl=sys.argv[1]; heroes=sys.argv[2:]
K=lambda r: cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(2*r+1,2*r+1))
esa=np.load(f"data/{lvl}_esa.npy"); dem=np.load(f"data/{lvl}_dem.npy"); n=dem.shape[0]
R,G,B,NIR,ev=esa
# ESA tiles leave 1-2 px gaps along their seams after reprojection: close them
gap=(cv2.morphologyEx((ev>0).astype(np.uint8),cv2.MORPH_CLOSE,K(2))>0)&(ev==0)
if gap.any():
    for ch in (R,G,B,NIR):
        s_=cv2.blur(np.where(ev>0,ch,0).astype(np.float32),(5,5)); w_=cv2.blur((ev>0).astype(np.float32),(5,5))
        ch[gap]=(s_/np.maximum(w_,1e-4))[gap]
    ev[gap]=1
ndvi=(NIR-R)/np.maximum(NIR+R,1e-4)
land=(ev>0)&(NIR>0.08)&(NIR>B*1.25)&((ndvi>0.2)|(R>0.1))
land=cv2.morphologyEx(land.astype(np.uint8),cv2.MORPH_OPEN,K(1)).astype(bool)
# hero water mosaic
hero=np.zeros((3,n,n),np.float32); hv=np.zeros((n,n),bool); hland=np.zeros((n,n),bool)
for s in heroes:
    a=np.load(f"data/{lvl}_{s}.npy"); rgb=a[:3].astype(np.float32)/1e4; scl=a[3]
    ok=(scl>0)&~hv
    cl=cv2.dilate(np.isin(scl,[3,8,9,10]).astype(np.uint8),K(2)).astype(bool)
    for i in range(3): hero[i][ok]=rgb[i][ok]
    hland[ok&~cl]=(scl[ok&~cl]==4); hv|=ok
    hcloud=locals().get('hcloud',np.zeros((n,n),bool)); hcloud[ok]=cl[ok]
water_h=hv&~land
lut_path="data/water_lut.json"
# DEM fallback: empty terrain tiles read as exactly 0 m -> borrow the coarser level's bathymetry
if lvl=="L1" and os.path.exists("data/L0_dem.npy"):
    sys.path.insert(0,"tools"); from geo import LEVELS
    L=dict((a,(b,c)) for a,b,c in LEVELS); h0,p0=L["L0"]; h1,p1=L["L1"]
    d0=np.load("data/L0_dem.npy"); c0=(h0-h1)/p0; sz=2*h1/p0
    crop=d0[int(c0):int(c0+sz)+2,int(c0):int(c0+sz)+2]
    up=cv2.resize(crop,(n,n),interpolation=cv2.INTER_CUBIC)
    flat=(np.abs(dem)<0.5)&~land; flat=cv2.morphologyEx(flat.astype(np.uint8),cv2.MORPH_OPEN,K(5)).astype(bool)
    dem=np.where(flat,np.minimum(up,-1),dem)
px_m=dict(LG=1800,L0=800,L1=100,L2=10)[lvl]
# terrain-tile bathymetry has gridded artefacts offshore: smooth it (sea only), ~4 km
sea_dem=cv2.GaussianBlur(np.where(land,0,dem).astype(np.float32),(0,0),max(1,(12000 if lvl in ('L0','LG') else 4000)/px_m))
depth=np.clip(-sea_dem,0,None)
if water_h.sum()>10000:
    lum=hero.mean(0); good=water_h&(lum<np.percentile(lum[water_h],97))&(lum>np.percentile(lum[water_h],3))
    bins=np.arange(0,81,2.0); lut=[]
    for b0 in bins:
        m=good&(depth>=b0)&(depth<b0+2)
        lut.append([float(np.median(hero[i][m])) if m.sum()>200 else None for i in range(3)])
    last=None
    for i,v in enumerate(lut):
        if v[0] is None: lut[i]=last
        else: last=v
    first=next(v for v in lut if v is not None); lut=[v or first for v in lut]
    json.dump({"bins":bins.tolist(),"rgb":lut},open(lut_path,"w"))
L_=json.load(open(lut_path)); bins=np.array(L_["bins"]); lut=np.array(L_["rgb"])
deep=lut[-1]
# beyond the shelf the sea keeps darkening toward open-ocean navy
# hero LUT is reliable to ~30 m (Belitung shelf); deeper the samples are few and hazy, so the
# palette continues toward shelf-sea teal-blue and open-ocean navy (true-colour reference values)
lut=np.array([np.convolve(lut[:,i],np.ones(5)/5,mode="same") for i in range(3)]).T
keep=(bins<=30)&(bins>=10)
pb=np.r_[bins[keep],50,120,400,1500]; pc=np.vstack([lut[keep],[0.020,0.036,0.058],[0.015,0.029,0.052],[0.011,0.022,0.046],[0.010,0.020,0.044]])
synth=np.stack([np.interp(depth,pb,pc[:,i]) for i in range(3)])
# large-scale structure (domain-warped fractal noise) so the open sea is not flat
rng=np.random.default_rng(7)
def fbm(oct_sizes):
    out=np.zeros((n,n),np.float32)
    for cells,amp in oct_sizes:
        g=rng.standard_normal((cells,cells)).astype(np.float32)
        out+=amp*cv2.resize(g,(n,n),interpolation=cv2.INTER_CUBIC)
    return out
wx=fbm([(6,1.0),(14,0.5)])*n*0.02; wy=fbm([(6,1.0),(14,0.5)])*n*0.02
base=fbm([(5,1.0),(12,0.6),(30,0.35),(80,0.2),(200,0.1)])
mx,my=np.meshgrid(np.arange(n,dtype=np.float32),np.arange(n,dtype=np.float32))
nz=cv2.remap(base,mx+wx,my+wy,cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT); nz/=nz.std()+1e-6
synth=synth*(1+0.035*nz[None]); synth[1]*=1+0.015*nz
if lvl=="L1" and os.path.exists("data/L0_water.npy"):
    L_=dict((a,(b,c)) for a,b,c in LEVELS); h0,p0=L_["L0"]; h1,p1=L_["L1"]
    w0=np.load("data/L0_water.npy"); c0=(h0-h1)/p0; sz=2*h1/p0
    M=np.array([[sz/n,0,c0-0.5+0.5*sz/n],[0,sz/n,c0-0.5+0.5*sz/n]],np.float32)
    up=np.stack([cv2.warpAffine(w0[i],M,(n,n),flags=cv2.INTER_CUBIC|cv2.WARP_INVERSE_MAP) for i in range(3)])
    det=synth/np.maximum(cv2.GaussianBlur(synth.transpose(1,2,0),(0,0),20).transpose(2,0,1),1e-4)
    synth=up*np.clip(det,0.9,1.1)
if lvl=="L0": np.save("data/L0_water.npy",synth.astype(np.float32))            # turbidity reads slightly greener
# hero water: remove clouds over the sea (bright, colourless) and SCL shadows, push-pull fill
if hv.any():
    a_scl=None
    spread=hero.max(0)-hero.min(0); lum=hero.mean(0)
    bg=cv2.GaussianBlur(np.where(water_h,lum,0),(0,0),15)/np.maximum(cv2.GaussianBlur(water_h.astype(np.float32),(0,0),15),1e-4)
    bad=water_h&(hcloud|((lum>bg*1.15)&(spread<0.04))|(lum<bg*0.8))
    bad=cv2.dilate(bad.astype(np.uint8),K(2)).astype(bool)
    okw=water_h&~bad
    def pushpull(img,valid):
        if min(valid.shape)<8 or valid.all(): return img
        w=valid.astype(np.float32); num=img*w[...,None]; sz=(w.shape[1]//2,w.shape[0]//2)
        sw=cv2.resize(w,sz,interpolation=cv2.INTER_AREA); sn=cv2.resize(num,sz,interpolation=cv2.INTER_AREA)
        sv=sw>1e-3; si=pushpull(np.where(sv[...,None],sn/np.maximum(sw,1e-6)[...,None],0),sv)
        return np.where(valid[...,None],img,cv2.resize(si,(w.shape[1],w.shape[0])))
    filled=pushpull(hero.transpose(1,2,0),okw).transpose(2,0,1)
    # feather hero water into synthetic sea over ~8 km
    from geo import xy
    half,px=dict((a,(b,c)) for a,b,c in LEVELS)[lvl]
    bx,by=xy(107.93,-2.86)                     # Belitung centre: hero water only on its shelf
    yy,xx=np.mgrid[0:n,0:n]; d=np.hypot(-half+(xx+.5)*px-bx,half-(yy+.5)*px-by)
    dist=cv2.distanceTransform((hv&~land).astype(np.uint8),cv2.DIST_L2,5)*px
    wgt=np.clip(dist/10000,0,1)*np.clip((70000-d)/25000,0,1); wgt=wgt**1.5
    # only the turquoise shelf comes from the hero scenes; their deep water is left to the common sea
    turq=cv2.GaussianBlur(np.clip((filled[1]/np.maximum(filled[2],1e-4)-0.82)/0.2,0,1).astype(np.float32),(0,0),3000/px)
    wgt=wgt*turq
    # match synthetic to hero right at the seam
    seam=(wgt>0.3)&(wgt<0.7)&okw&(depth>15)
    if seam.sum()>1000:
        for i in range(3): synth[i]*=np.median(filled[i][seam])/max(np.median(synth[i][seam]),1e-4)
    water=synth*(1-wgt)+filled*wgt
else: water=synth
# ESA tiles (1x1 deg) differ slightly in tone: level each tile's land toward the smooth regional tone
sys.path.insert(0,"tools"); from geo import LEVELS, lonlat
_h,_p=dict((a,(b,c)) for a,b,c in LEVELS)[lvl]
st=8 if n>2000 else 4
gy,gx=np.mgrid[0:n:st,0:n:st]; glo,gla=lonlat(-_h+(gx+.5)*_p,_h-(gy+.5)*_p)
tid=cv2.resize((np.floor(glo).astype(np.int32)*1000+np.floor(gla).astype(np.int32)+500000).astype(np.float32),(n,n),interpolation=cv2.INTER_NEAREST).astype(np.int64)
landf=land.astype(np.float32)
uid,inv=np.unique(tid,return_inverse=True); inv=inv.reshape(tid.shape)
lw=np.bincount(inv[land],minlength=len(uid)).astype(np.float64)
for i,ch in enumerate((R,G,B)):
    sig=max(3,int(1.5*111000/_p))
    f=max(1,sig//8); sm_=lambda a: cv2.resize(cv2.GaussianBlur(cv2.resize(a,(n//f,n//f),interpolation=cv2.INTER_AREA),(0,0),sig/f),(n,n),interpolation=cv2.INTER_LINEAR)
    smooth=sm_(np.where(land,ch,0).astype(np.float32))/np.maximum(sm_(landf),1e-4)
    tm=np.bincount(inv[land],weights=ch[land],minlength=len(uid))/np.maximum(lw,1)
    sm=np.bincount(inv[land],weights=smooth[land],minlength=len(uid))/np.maximum(lw,1)
    g=np.where(lw>200,sm/np.maximum(tm,1e-4),1.0); g=np.clip(g,0.75,1.33)
    ch*=np.where(land,g[inv],1).astype(np.float32)
print("tiles levelled")
# land: ESA, colour-matched to the hero land (only where hero land is clear)
landrgb=np.stack([R,G,B])
if lvl=="L1" and os.path.exists("data/L2_comp.npy"):
    # match ESA land to the Seliu-level hero land (what the camera lands on), same area, same 100 m scale
    L_=dict((a,(b,c)) for a,b,c in LEVELS); h2,p2=L_["L2"]; h1,p1=L_["L1"]
    A=np.load("data/L2_comp.npy",mmap_mode="r"); k=int(p1/p2); m2=A.shape[1]//k
    hs=np.stack([cv2.resize(np.array(A[i]),(m2,m2),interpolation=cv2.INTER_AREA) for i in range(4)])
    c0=int(round((h1-h2)/p1)); sl=(slice(c0,c0+m2),slice(c0,c0+m2))
    m=(hs[3]>0.9)&land[sl]
    lm=[]
    for i in range(3):
        sx=np.percentile(landrgb[i][sl][m],[10,90]); sy=np.percentile(hs[i][m],[10,90])
        g=(sy[1]-sy[0])/(sx[1]-sx[0]); o=sy[0]-sx[0]*g; landrgb[i]=landrgb[i]*g+o; lm.append([float(g),float(o)])
    json.dump(lm,open("data/land_match.json","w")); print("land matched to L2",lm)
elif hv.any() and False:
    m=land&hland
    if m.sum()>5000:
        for i in range(3):
            sx=np.percentile(landrgb[i][m],[10,90]); sy=np.percentile(hero[i][m],[10,90])
            g=(sy[1]-sy[0])/(sx[1]-sx[0]); o=sy[0]-sx[0]*g; landrgb[i]=landrgb[i]*g+o
            lmatch=locals().get('lmatch',[]); lmatch.append([float(g),float(o)])
        json.dump(lmatch,open("data/land_match.json","w"))
elif os.path.exists("data/land_match.json"):
    lm=json.load(open("data/land_match.json"))
    for i in range(3): landrgb[i]=landrgb[i]*lm[i][0]+lm[i][1]
# soft coastline
la=cv2.GaussianBlur(land.astype(np.float32),(0,0),0.8)
tex=landrgb*la+water*(1-la)
np.save(f"data/{lvl}_tex.npy",np.concatenate([tex,land[None]]).astype(np.float32))
print("done",lvl)
