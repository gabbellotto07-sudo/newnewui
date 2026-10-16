"""Cloud-free composite of a level.
Hero scene (first) defines the look. Clouds + cloud shadows (SCL 3,8,9,10) are cut out:
  - over land the holes are filled from later scenes, colour-matched to the hero;
  - over water the holes are inpainted from surrounding hero water (other dates' water
    has different sediment plumes and would show as patches).
usage: composite.py LEVEL out.npy HERO [FILL...] -> float32 R,G,B reflectance + land mask"""
import sys, numpy as np, cv2
lvl,out=sys.argv[1],sys.argv[2]; scenes=sys.argv[3:]
K=lambda r: cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(2*r+1,2*r+1))
def load(s):
    a=np.load(f"data/{lvl}_{s}.npy",mmap_mode="r"); rgb=(a[:3].astype(np.float32)/10000.0); scl=np.array(a[3])
    bad=np.isin(scl,[3,8,9,10]); bad=cv2.dilate(bad.astype(np.uint8),K(6)).astype(bool)|(scl==0)
    return rgb,scl,~bad
H,Hs,Hok=load(scenes[0])
land=np.isin(Hs,[4,5,7,11,1,2])
fills=[load(s) for s in scenes[1:]]
# land/water vote for hero holes from fill scenes
for F,Fs,Fok in fills:
    m=~Hok&Fok; land[m]=np.isin(Fs[m],[4,5,7,11,1,2])
land=cv2.morphologyEx(land.astype(np.uint8),cv2.MORPH_OPEN,K(1)).astype(bool)
acc=H.copy(); have=Hok.copy()
for (F,Fs,Fok),s in zip(fills,scenes[1:]):
    both=Hok&Fok&land
    if both.sum()>5000:
        for i in range(3):
            sx=np.percentile(F[i][both],[5,95]); sy=np.percentile(H[i][both],[5,95])
            F[i]=(F[i]-sx[0])*(sy[1]-sy[0])/max(sx[1]-sx[0],1e-4)+sy[0]
    m=~have&Fok&land
    for i in range(3): acc[i][m]=F[i][m]
    have|=m; print(s,"land fill",m.mean(),flush=True)
# water: SCL misses many small cumulus and most of their shadows over the sea.
# Flag water pixels that are much darker / brighter than the local water background.
# Over the sea the hero is kept as photographed (distant cumulus are real weather).
# Only inside the "stage" (the strait and Seliu, where the camera lands) clouds and their
# shadows are removed: SCL cloud/shadow + blobs that are uniformly darker / colourless brighter.
water=~land
sys.path.insert(0,"tools"); from geo import xy, PLACES, LEVELS
half,px=dict((n,(h,p)) for n,h,p in LEVELS)[lvl]; n=H.shape[1]
yy,xx=np.mgrid[0:n,0:n].astype(np.float32); X=-half+(xx+.5)*px; Y=half-(yy+.5)*px
cx,cy=[(a+b)/2 for a,b in zip(xy(*PLACES["seliu"]),xy(*PLACES["teluk_gembira_pier"]))]
stage=np.hypot(X-cx,Y-cy)<9000; del X,Y,xx,yy
# clean plate: clouds/shadows inside the stage, picked by eye on review/L2_stage_grid.jpg
import json, os
anom=np.zeros(water.shape,bool)
cp=f"tools/cleanplate_{lvl}.json"
if os.path.exists(cp):
    for x0,y0,r0 in json.load(open(cp)): cv2.circle(anom.view(np.uint8),(int(x0),int(y0)),int(r0),1,-1)
# Open (deep, blue-dominant) sea: no reefs to confuse, so trust SCL there plus a uniform-darkening shadow test.
# Shallow/turquoise water: SCL calls bright reef flats 'cloud' -> give that water back to the hero.
bg=lambda x: cv2.GaussianBlur(np.where(water,x,0).astype(np.float32),(0,0),25)/np.maximum(cv2.GaussianBlur(water.astype(np.float32),(0,0),25),1e-4)
bgw=lambda x,sg: cv2.GaussianBlur(np.where(water&Hok,x,0).astype(np.float32),(0,0),sg)/np.maximum(cv2.GaussianBlur((water&Hok).astype(np.float32),(0,0),sg),1e-4)
bB,bG=bgw(H[2],80),bgw(H[1],80); deep=water&(bB>bG*1.06)&~cv2.dilate(land.astype(np.uint8),K(60)).astype(bool)
deep=cv2.erode(deep.astype(np.uint8),K(10)).astype(bool)
r=np.stack([H[i]/np.maximum(bg(H[i]),1e-4) for i in range(3)])
dshadow=deep&((r.mean(0)<0.94)|(r.mean(0)>1.04)); del r
dshadow=cv2.dilate(cv2.morphologyEx(dshadow.astype(np.uint8),cv2.MORPH_OPEN,K(1)),K(9)).astype(bool)&deep
sclbad=~Hok&water&~deep&(Hs>0)
have|=sclbad
for i in range(3): acc[i][sclbad]=H[i][sclbad]
have&=~dshadow
print("deep sea",deep.mean(),"extra shadows",dshadow.mean())
anom&=water
have&=~anom; print("water anomalies",anom.mean())
# big clean-plate areas over shallows: take reefs from the other dates (stable), colour-matched on water
big=anom&~stage&water
for (F,Fs,Fok),sname in zip(fills,scenes[1:]):
    tgt=big&~have&Fok
    if tgt.sum()==0: continue
    ring=cv2.dilate(big.astype(np.uint8),K(40)).astype(bool)&~big&water&Fok&Hok
    if ring.sum()<2000: continue
    G_=np.empty_like(F)
    for i in range(3):
        sx=np.percentile(F[i][ring],[10,90]); sy=np.percentile(H[i][ring],[10,90])
        G_[i]=(F[i]-sx[0])*(sy[1]-sy[0])/max(sx[1]-sx[0],1e-4)+sy[0]
    soft=cv2.GaussianBlur(tgt.astype(np.float32),(0,0),6)
    for i in range(3): acc[i]=np.where(tgt|((soft>0)&big),acc[i]*(1-soft)+G_[i]*soft,acc[i])
    have|=tgt; print("shallow fill from",sname,tgt.mean())
del fills
# water holes (and any remaining) -> push-pull fill from surrounding hero water
hole=~have
def pushpull(img,valid):
    """fill invalid pixels by multiscale normalised averaging (smooth, no seams)"""
    if min(valid.shape)<8 or valid.all(): return img
    w=valid.astype(np.float32); num=img*w[...,None]
    sw=cv2.resize(w,(w.shape[1]//2,w.shape[0]//2),interpolation=cv2.INTER_AREA)
    sn=cv2.resize(num,(w.shape[1]//2,w.shape[0]//2),interpolation=cv2.INTER_AREA)
    sv=sw>1e-3; si=np.where(sv[...,None],sn/np.maximum(sw,1e-6)[...,None],0)
    si=pushpull(si,sv)
    up=cv2.resize(si,(w.shape[1],w.shape[0]),interpolation=cv2.INTER_LINEAR)
    return np.where(valid[...,None],img,up)
f=4; small=cv2.resize(acc.transpose(1,2,0),None,fx=1/f,fy=1/f,interpolation=cv2.INTER_AREA)
hs=cv2.resize(hole.astype(np.float32),(small.shape[1],small.shape[0]),interpolation=cv2.INTER_AREA)>0
fill=pushpull(small,~hs)
fill=np.where(hs[...,None],cv2.GaussianBlur(fill,(0,0),3),fill)
fillU=cv2.resize(fill,(acc.shape[2],acc.shape[1]),interpolation=cv2.INTER_CUBIC).transpose(2,0,1)
a=cv2.GaussianBlur(hole.astype(np.float32),(0,0),4); a=np.maximum(a,hole)
acc=acc*(1-a)+fillU*a
print("water inpainted",hole.mean())
import PIL.Image as I; I.fromarray((anom[::5,::5]*255).astype(np.uint8)).save(f"review/{lvl}_anom.png")
np.save(out,np.concatenate([acc,land[None].astype(np.float32)]).astype(np.float32))
