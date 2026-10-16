"""Belitung level LM (+-90 km around Seliu, 15 m): the level the camera crosses in the dive.
  land  = per-pixel median of the clear Sentinel-2 passes of 2026 (SCL vegetation / not-vegetated only),
          so tin mines, roads and clearings stay exactly as they are today; nothing is added or removed
  water = the hero scene of 29-07-2019 (same water as L1 and L2), its clouds and cloud shadows filled
          from the surrounding water (smooth push-pull, open sea only)
  clouds = the real clouds of 29-07-2019 as alpha (for the 3D cloud layer), like extract_clouds.py
  then L2 (Seliu, 10 m) is written into the centre with the renderer's feather, so the switch L2<->LM
  changes sharpness only, never colour.
usage: build_lm.py HERO_DATE LAND_DATE [LAND_DATE ...] -> data/LM_tex.npy (R,G,B,land) float32, data/LM_clouds.npy"""
import sys, os, numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geo import LEVELS
K = lambda r: cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*r+1, 2*r+1))
L = dict((a, (b, c)) for a, b, c in LEVELS); half, px = L["LM"]; n = int(2*half/px)
hero_d, land_ds = sys.argv[1], sys.argv[2:]
H = np.load(f"data/LM_{hero_d}.npy", mmap_mode="r")
Ds = [np.load(f"data/LM_{d}.npy", mmap_mode="r") for d in land_ds]
CLOUD = [0, 1, 2, 3, 8, 9, 10, 11]          # no data, saturated, dark/shadow, cloud shadow, clouds, cirrus, snow

# ---------------------------------------------------------------- land mask (votes over all dates) + land median
CACHE = "data/LM_landmedian.npz"
votes_land = np.zeros((n, n), np.int16); votes_water = np.zeros((n, n), np.int16)
land_rgb = np.zeros((3, n, n), np.float32); nobs = np.zeros((n, n), np.int16)
S = 400
cached = os.path.exists(CACHE)
if cached:
    z = np.load(CACHE); land_rgb = z["rgb"].astype(np.float32); nobs = z["nobs"]; votes_land = z["vl"]; votes_water = z["vw"]; del z
    print("land median from cache", flush=True)
for r0 in (range(0, n, S) if not cached else []):
    sl = slice(r0, min(n, r0+S))
    stack = []; oks = []
    for A in Ds+[H]:
        scl = np.array(A[3, sl]); votes_land[sl] += np.isin(scl, [4, 5]); votes_water[sl] += (scl == 6)
    for A in Ds:
        scl = np.array(A[3, sl]); ok = np.isin(scl, [4, 5])
        # thin haze that SCL keeps as land: bright and colourless -> reject
        rgb = np.array(A[:3, sl]).astype(np.float32)/1e4
        ok &= ~((rgb.mean(0) > 0.16) & (np.abs(rgb[0]-rgb[2]) < 0.025) & (rgb[1] < rgb[0]*1.05))
        stack.append(np.where(ok[None], rgb, np.nan)); oks.append(ok)
    st = np.stack(stack)                                   # (D,3,rows,n)
    with np.errstate(all="ignore"):
        land_rgb[:, sl] = np.nan_to_num(np.nanmedian(st, axis=0))
    nobs[sl] = np.sum(oks, axis=0)
    print("land rows", r0, flush=True)
if not cached:
    np.savez(CACHE, rgb=land_rgb.astype(np.float16), nobs=nobs, vl=votes_land, vw=votes_water)
land = votes_land > votes_water
del votes_land, votes_water
land = cv2.morphologyEx(land.astype(np.uint8), cv2.MORPH_OPEN, K(1)).astype(bool)

def pushpull(img, valid):
    """fill invalid pixels by multiscale normalised averaging (smooth, no seams)"""
    if min(valid.shape) < 8 or valid.all(): return img
    w = valid.astype(np.float32); num = img*w[..., None]; sz = (w.shape[1]//2, w.shape[0]//2)
    sw = cv2.resize(w, sz, interpolation=cv2.INTER_AREA); sn = cv2.resize(num, sz, interpolation=cv2.INTER_AREA)
    sv = sw > 1e-3; si = pushpull(np.where(sv[..., None], sn/np.maximum(sw, 1e-6)[..., None], 0), sv)
    return np.where(valid[..., None], img, cv2.resize(si, (w.shape[1], w.shape[0]), interpolation=cv2.INTER_LINEAR))

def fill(img, valid, f=4):
    """push-pull computed at 1/f resolution, written only into the invalid pixels (memory-light)"""
    h, w = valid.shape; sz = (w//f, h//f)
    num = cv2.resize(img*valid[..., None], sz, interpolation=cv2.INTER_AREA)
    wt = cv2.resize(valid.astype(np.float32), sz, interpolation=cv2.INTER_AREA)
    sv = wt > 1e-3; si = pushpull(np.where(sv[..., None], num/np.maximum(wt, 1e-6)[..., None], 0), sv); del num
    up = cv2.resize(si, (w, h), interpolation=cv2.INTER_LINEAR)
    inv = ~valid; img[inv] = up[inv]; del up
    return img

def pushpull2(img, valid):
    """2D push-pull (single channel)"""
    if min(valid.shape) < 8 or valid.all(): return img
    w = valid.astype(np.float32); sz = (w.shape[1]//2, w.shape[0]//2)
    sw = cv2.resize(w, sz, interpolation=cv2.INTER_AREA); sn = cv2.resize(img*w, sz, interpolation=cv2.INTER_AREA)
    sv = sw > 1e-3; si = pushpull2(np.where(sv, sn/np.maximum(sw, 1e-6), 0).astype(np.float32), sv)
    return np.where(valid, img, cv2.resize(si, (w.shape[1], w.shape[0]), interpolation=cv2.INTER_LINEAR))

def fill1(img, valid, f=4):
    """single channel push-pull at 1/f resolution, written into the invalid pixels in place"""
    h, w = valid.shape; sz = (w//f, h//f)
    num = cv2.resize(np.where(valid, img, 0).astype(np.float32), sz, interpolation=cv2.INTER_AREA)
    wt = cv2.resize(valid.astype(np.float32), sz, interpolation=cv2.INTER_AREA)
    sv = wt > 1e-3
    si = pushpull2(np.where(sv, num/np.maximum(wt, 1e-6), 0).astype(np.float32), sv)
    up = cv2.resize(si, (w, h), interpolation=cv2.INTER_LINEAR)
    np.copyto(img, up, where=~valid); del up
    return img

print("land without a clear 2026 pass", float((land & (nobs == 0)).sum()/max(land.sum(), 1)), flush=True)
lvalid = land & (nobs > 0); del nobs
for c in range(3): fill1(land_rgb[c], lvalid)
del lvalid
# ---------------------------------------------------------------- hero water: per channel, clouds out
water = ~land
hs = np.array(H[3])
hc = [np.array(H[c]).astype(np.float32)/1e4 for c in range(3)]
lum = (hc[0]+hc[1]+hc[2])/3
spread = np.maximum(np.maximum(hc[0], hc[1]), hc[2])-np.minimum(np.minimum(hc[0], hc[1]), hc[2])
wm = water & (hs == 6)
wbg = cv2.GaussianBlur(np.where(wm, lum, 0).astype(np.float32), (0, 0), 20)/np.maximum(cv2.GaussianBlur(wm.astype(np.float32), (0, 0), 20), 1e-4)
del wm
grey_bright = (lum > wbg*1.12) & (spread < 0.045)
turq = (hc[1] > hc[0]*1.15) & (hc[2] > hc[0]*1.1) & (spread > 0.03)
bad = water & ((np.isin(hs, [0, 3, 8, 9, 10]) & ~turq) | grey_bright | ((lum < wbg*0.82) & water))
del turq, wbg
bad = cv2.dilate(bad.astype(np.uint8), K(3)).astype(bool) & water
wvalid = water & ~bad
print("water cloud/shadow filled", float(bad.sum()/max(water.sum(), 1)), flush=True)
cand_cl = np.isin(hs, [8, 9, 10]) | grey_bright
del bad, grey_bright, hs
# ---------------------------------------------------------------- compose straight to disk
out = np.lib.format.open_memmap("data/LM_tex.npy", mode="w+", dtype=np.float32, shape=(4, n, n))
la = cv2.GaussianBlur(land.astype(np.float32), (0, 0), 0.8)
ground_lum = np.zeros((n, n), np.float32)
for c in range(3):
    wch = fill1(hc[c].copy(), wvalid)
    out[c] = land_rgb[c]*la+wch*(1-la)
    ground_lum += out[c]/3
    del wch
out[3] = land.astype(np.float32)
del wvalid, la, land_rgb
# ---------------------------------------------------------------- real clouds as alpha (3D layer)
x = np.clip((lum-ground_lum-0.015)/0.22, 0, 1); x = x*x*(3-2*x)
del ground_lum, lum
grey = np.clip(1-(spread-0.03)/0.08, 0, 1); del spread
cand = cv2.GaussianBlur(cv2.dilate(cand_cl.astype(np.uint8), K(2)).astype(np.float32), (0, 0), 1.5); del cand_cl
alpha = cv2.GaussianBlur((x*grey*cand).astype(np.float32), (0, 0), 0.7); del x, grey, cand, hc
np.save("data/LM_clouds.npy", alpha.astype(np.float16)); print("cloud cover >0.3", float((alpha > 0.3).mean()), flush=True)
cv2.imwrite("review/LM_clouds.jpg", (np.clip(alpha[::8, ::8], 0, 1)*255).astype(np.uint8)); del alpha
# ---------------------------------------------------------------- write L2 (Seliu, 10 m) into the centre
h2, p2 = L["L2"]
A = np.load("data/L2_comp.npy", mmap_mode="r")
side = int(np.ceil(2*h2/px))+2; c0 = int(np.floor((half-h2)/px))-1
off = ((-half+(c0+0.5)*px)+h2)/p2-0.5
M = np.array([[px/p2, 0, off], [0, px/p2, off]], np.float32)
yy, xx = np.mgrid[0:side, 0:side].astype(np.float32)
X = -half+(c0+xx+.5)*px; Y = half-(c0+yy+.5)*px
e = np.maximum(np.abs(X), np.abs(Y))/h2
w = np.clip((1-e)/0.25, 0, 1)*np.clip((30000-np.hypot(X, Y))/14000, 0, 1)
sl = (slice(c0, c0+side), slice(c0, c0+side))
for c in range(4):
    a = cv2.GaussianBlur(np.array(A[c]), (0, 0), 0.6) if c < 3 else np.array(A[c])
    small = cv2.warpAffine(a, M, (side, side), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)
    if c < 3: out[c][sl] = out[c][sl]*(1-w)+small*w
    else: out[3][sl] = np.where(w > 0.5, small, out[3][sl])
out.flush()
v = np.clip(np.stack([out[c][::8, ::8] for c in range(3)], -1)*3.0, 0, 1)**(1/2.2)
cv2.imwrite("review/LM_tex.jpg", cv2.cvtColor((v*255).astype(np.uint8), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 88])
print("done LM", n, flush=True)
