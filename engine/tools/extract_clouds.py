"""Lift the real clouds of the hero day (29-07-2019) off the ground so the renderer can put them back
in 3D (~1 km up, with their shadows): alpha = how much brighter and greyer the photographed scene is
than the cleaned ground, only where Sentinel-2 itself (SCL) or our clean plate says "cloud".
usage: extract_clouds.py LEVEL GROUND.npy HERO [HERO2...] -> data/<LEVEL>_clouds.npy (float16 alpha)"""
import sys, os, json, numpy as np, cv2
lvl, gp = sys.argv[1], sys.argv[2]; heroes = sys.argv[3:]
K = lambda r: cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*r+1, 2*r+1))
G = np.load(gp, mmap_mode="r"); n = G.shape[1]
hero = np.zeros((3, n, n), np.float32); scl = np.zeros((n, n), np.uint16); hv = np.zeros((n, n), bool)
for s in heroes:
    a = np.load(f"data/{lvl}_{s}.npy", mmap_mode="r"); sc = np.array(a[3]); ok = (sc > 0) & ~hv
    for i in range(3): hero[i][ok] = a[i][ok]/1e4
    scl[ok] = sc[ok]; hv |= ok
cand = np.isin(scl, [8, 9, 10]).astype(np.uint8)
cp = f"tools/cleanplate_{lvl}.json"
if os.path.exists(cp) and lvl == "L2":
    m = np.zeros((n, n), np.uint8)
    for x, y, r in json.load(open(cp)):
        if r <= 60: cv2.circle(m, (x, y), r, 1, -1)       # only the hand-picked single clouds
    cand |= m
r = 2 if lvl == "L2" else 1
cand = cv2.dilate(cand, K(r)).astype(np.float32)
cand = cv2.GaussianBlur(cand, (0, 0), r)
lh = hero.mean(0); lg = np.array(G[:3]).mean(0)
spread = hero.max(0)-hero.min(0)
x = np.clip((lh-lg-0.015)/0.22, 0, 1); x = x*x*(3-2*x)
grey = np.clip(1-(spread-0.03)/0.08, 0, 1)
alpha = (x*grey*cand).astype(np.float32)
alpha = cv2.GaussianBlur(alpha, (0, 0), 0.7)
np.save(f"data/{lvl}_clouds.npy", alpha.astype(np.float16))
print(lvl, "cloud cover >0.3:", float((alpha > 0.3).mean()))
cv2.imwrite(f"review/{lvl}_clouds.jpg", (alpha[::max(1, n//1400), ::max(1, n//1400)]*255).astype(np.uint8))
