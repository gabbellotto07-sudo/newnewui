"""Bring the land of the Seliu level up to date: the sea stays the limpid hero scene of 29-07-2019,
the land (Seliu and the Belitung coast) comes from the most recent clear Sentinel-2 passes, so the
island is shown as it is today (e.g. the clearings opened on Seliu after 2019).
usage: land_update.py SCENE_NEWEST [SCENE ...]   (priority order)  -> rewrites data/L2_comp.npy"""
import sys, numpy as np, cv2
K = lambda r: cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*r+1, 2*r+1))
C = np.load("data/L2_comp.npy"); land = C[3] > 0.5
done = np.zeros(land.shape, bool); acc = C[:3].copy(); wsum = np.zeros(land.shape, np.float32)
base = C[:3]
inner = cv2.erode(land.astype(np.uint8), K(2)).astype(bool)        # keep the hero's exact shoreline
for s in sys.argv[1:]:
    a = np.load(f"data/L2_{s}.npy", mmap_mode="r"); scl = np.array(a[3]); rgb = np.array(a[:3]).astype(np.float32)/1e4
    bad = np.isin(scl, [0, 1, 3, 8, 9, 10, 6]) | ((rgb.mean(0) > 0.16) & (np.abs(rgb[0]-rgb[2]) < 0.03))
    bad = cv2.dilate(bad.astype(np.uint8), K(10)).astype(bool)
    ok = land & ~bad & ~done
    both = land & ~bad
    if ok.sum() < 1000: continue
    for i in range(3):                                            # match tone to the hero land (same look)
        sx = np.percentile(rgb[i][both], [10, 90]); sy = np.percentile(base[i][both], [10, 90])
        rgb[i] = (rgb[i]-sx[0])*(sy[1]-sy[0])/max(sx[1]-sx[0], 1e-4)+sy[0]
    w = cv2.GaussianBlur(ok.astype(np.float32), (0, 0), 3)*ok
    for i in range(3): acc[i] = np.where(ok, rgb[i], acc[i])
    wsum = np.maximum(wsum, w); done |= ok
    print(s, "land updated", ok.sum()/max(land.sum(), 1))
# soft edges where recent land meets older land (cloud holes) and at the shore band
wt = cv2.GaussianBlur((done & inner).astype(np.float32), (0, 0), 4)*land
for i in range(3): C[i] = base[i]*(1-wt)+acc[i]*wt
np.save("data/L2_comp.npy", C); print("recent land share", float(done[land].mean()))
