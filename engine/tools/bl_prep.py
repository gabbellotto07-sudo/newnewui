"""Prepare data for the Blender scene (system Python, not Blender's).
Local frame: origin at Seliu centre (LAT0, LON0) on the sphere, axes x=East, y=North, z=Up.
Every vertex is placed on the real sphere (R_E + height), so curvature and the camera match render.Camera.

usage: bl_prep.py mesh [--step 4]              -> data/bl/L2_verts.npy, L2_uv.npy (grid), L2_albedo.npy, L2_cloud.npy
       bl_prep.py cams OUT.json t1 t2 ...       (SELIU_FMT selects 16x9 / 9x16)
       bl_prep.py cam  OUT.json lat lon range_km heading tilt vfov
"""
import sys, os, json, math, numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geo import LON0, LAT0
R_E = 6371008.8
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda *p: os.path.join(ROOT, "data", *p)
PH0, LM0 = math.radians(LAT0), math.radians(LON0)

def ecef(lat, lon, h=0.0):
    la, lo = np.radians(lat), np.radians(lon); r = R_E+h
    return np.stack([r*np.cos(la)*np.cos(lo), r*np.cos(la)*np.sin(lo), r*np.sin(la)], -1)

E0 = np.array([-math.sin(LM0), math.cos(LM0), 0.0])
N0 = np.array([-math.sin(PH0)*math.cos(LM0), -math.sin(PH0)*math.sin(LM0), math.cos(PH0)])
U0 = np.array([math.cos(PH0)*math.cos(LM0), math.cos(PH0)*math.sin(LM0), math.sin(PH0)])
O0 = ecef(LAT0, LON0)
def to_local(P): v = P-O0; return np.stack([v@E0, v@N0, v@U0], -1)
def dir_local(v): return np.array([v@E0, v@N0, v@U0])

def aeqd_inv(x, y):
    """spherical azimuthal equidistant (same as render.aeqd) -> lat, lon (deg)"""
    rho = np.hypot(x, y); c = rho/R_E
    with np.errstate(invalid="ignore", divide="ignore"):
        lat = np.arcsin(np.cos(c)*math.sin(PH0)+np.where(rho > 0, y*np.sin(c)*math.cos(PH0)/np.maximum(rho, 1e-9), 0))
        lon = LM0+np.arctan2(x*np.sin(c), rho*math.cos(PH0)*np.cos(c)-y*math.sin(PH0)*np.sin(c))
    return np.degrees(lat), np.degrees(lon)

def mesh(step):
    half, px = 32000, 10
    dem = np.load(D("L2_cop.npy")); n = dem.shape[0]
    C = np.load(D("L2_comp.npy"), mmap_mode="r"); land = np.array(C[3]) > 0.5
    # sea level is 0; DSM over land (canopy included). Soft shoreline so beaches meet the water
    h = np.where(cv2.GaussianBlur(land.astype(np.float32), (0, 0), 2) > 0.5, np.maximum(dem, 0.5), 0.0).astype(np.float32)
    h = cv2.GaussianBlur(h, (0, 0), 1.0)
    idx = np.arange(0, n, step); idx = np.r_[idx, n-1] if idx[-1] != n-1 else idx
    cc, rr = np.meshgrid(idx, idx)
    X = -half+(cc+0.5)*px; Y = half-(rr+0.5)*px
    lat, lon = aeqd_inv(X, Y)
    P = to_local(ecef(lat, lon, h[rr, cc].astype(np.float64)))
    os.makedirs(D("bl"), exist_ok=True)
    np.save(D("bl", "L2_verts.npy"), P.astype(np.float32))
    uv = np.stack([(cc+0.5)/n, 1-(rr+0.5)/n], -1).astype(np.float32)
    np.save(D("bl", "L2_uv.npy"), uv)
    # albedo: surface reflectance as RGBA, bottom-up rows for Blender, alpha = land
    rgba = np.concatenate([np.array(C[:3]), land[None].astype(np.float32)]).transpose(1, 2, 0)[::-1]
    np.save(D("bl", "L2_albedo.npy"), np.ascontiguousarray(rgba, np.float32))
    cl = np.load(D("L2_clouds.npy")).astype(np.float32)
    np.save(D("bl", "L2_cloud.npy"), np.ascontiguousarray(cloud_domes(cl, px)[::-1]))
    print("mesh", P.shape, "z range", float(P[..., 2].min()), float(P[..., 2].max()))

def mesh_lm(cx, cy, half, step_m=60.0, prefix="LMc"):
    """crop of the Belitung level LM (15 m) centred on (cx, cy) AEQD metres, +-half metres: mesh on the real
    sphere with GLO-30 relief, albedo, cloud dome heights (same rule as render_v8). For the Blender variant."""
    import render_v8 as R
    H0, P0 = 90000, 15
    T = np.load(D("LM_tex.npy"), mmap_mode="r"); n = T.shape[1]
    c0 = int(round((cx-half+H0)/P0)); r0 = int(round((H0-(cy+half))/P0)); m = int(round(2*half/P0))
    sl = (slice(r0, r0+m), slice(c0, c0+m))
    land = np.array(T[3][sl]) > 0.5
    dem = np.load(D("LM_cop.npy"), mmap_mode="r")[sl].astype(np.float32)
    h = np.where(cv2.GaussianBlur(land.astype(np.float32), (0, 0), 2) > 0.5, np.maximum(dem, 0.5), 0.0).astype(np.float32)
    h = cv2.GaussianBlur(h, (0, 0), 1.0)
    st = max(1, int(round(step_m/P0)))
    idx = np.arange(0, m, st); idx = np.r_[idx, m-1] if idx[-1] != m-1 else idx
    cc, rr = np.meshgrid(idx, idx)
    X = -H0+(c0+cc+0.5)*P0; Y = H0-(r0+rr+0.5)*P0
    lat, lon = aeqd_inv(X, Y)
    Pv = to_local(ecef(lat, lon, h[rr, cc].astype(np.float64)))
    os.makedirs(D("bl"), exist_ok=True)
    np.save(D("bl", f"{prefix}_verts.npy"), Pv.astype(np.float32))
    np.save(D("bl", f"{prefix}_uv.npy"), np.stack([(cc+0.5)/m, 1-(rr+0.5)/m], -1).astype(np.float32))
    rgba = np.stack([np.array(T[i][sl]) for i in range(3)]+[land.astype(np.float32)], -1)[::-1]
    np.save(D("bl", f"{prefix}_albedo.npy"), np.ascontiguousarray(rgba, np.float32))
    al = np.load(D("LM_clouds.npy"), mmap_mode="r")[sl].astype(np.float32)
    np.save(D("bl", f"{prefix}_cloud.npy"), np.ascontiguousarray(R.cloud_domes(al, P0)[::-1]))
    json.dump({"cx": cx, "cy": cy, "half": half, "base": R.CLOUD_BASE, "dome_max": R.DOME_MAX}, open(D("bl", f"{prefix}_meta.json"), "w"))
    print("mesh_lm", Pv.shape, "crop px", m)

def cloud_domes(a, px):
    """real cloud mask -> dome height (m) above the flat base. A cumulus of radius r rises ~0.8 r:
    h = 0.8*sqrt(r^2-(r-e)^2), e = distance to the cloud edge, r = local max of e (the cloud's own radius)."""
    m = (a > 0.25).astype(np.uint8)
    e = cv2.distanceTransform(m, cv2.DIST_L2, 5).astype(np.float32)*px
    r = cv2.dilate(e, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31)))
    h = 0.8*np.sqrt(np.clip(r*r-(r-e)**2, 0, None))
    h = np.minimum(h, 1500.0)*np.clip(a/0.5, 0, 1)
    return cv2.GaussianBlur(h, (0, 0), 1.0)

def cam_rec(lat, lon, rng, heading, tilt, vfov):
    """same construction as render.Camera, expressed in the local frame"""
    T = ecef(lat, lon)
    la, lo = math.radians(lat), math.radians(lon)
    e = np.array([-math.sin(lo), math.cos(lo), 0.0])
    nn = np.array([-math.sin(la)*math.cos(lo), -math.sin(la)*math.sin(lo), math.cos(la)])
    u = np.array([math.cos(la)*math.cos(lo), math.cos(la)*math.sin(lo), math.sin(la)])
    ps, ts = math.radians(heading), math.radians(tilt)
    hdir = math.sin(ps)*e+math.cos(ps)*nn
    fwd = math.sin(ts)*hdir-math.cos(ts)*u
    pos = T-rng*fwd
    right = math.cos(ps)*e-math.sin(ps)*nn
    up = np.cross(right, fwd); up /= np.linalg.norm(up)
    right = np.cross(fwd, up); right /= np.linalg.norm(right)
    return {"pos": to_local(pos).tolist(), "fwd": dir_local(fwd).tolist(), "up": dir_local(up).tolist(),
            "vfov": vfov, "alt": float(np.linalg.norm(pos)-R_E), "params": [lat, lon, rng, heading, tilt]}

if __name__ == "__main__":
    m = sys.argv[1]
    if m == "mesh_lm":
        mesh_lm(*map(float, sys.argv[2:5]))
    elif m == "mesh":
        mesh(int(sys.argv[sys.argv.index("--step")+1]) if "--step" in sys.argv else 4)
    elif m == "cams":
        import timeline as TL
        out = {f"{t:.3f}": dict(cam_rec(*TL.camera(t), TL.VFOV), t=t) for t in map(float, sys.argv[3:])}
        json.dump(out, open(sys.argv[2], "w"), indent=1)
    elif m == "cam":
        lat, lon, rkm, hd, tl, vf = map(float, sys.argv[3:9])
        json.dump({"x": dict(cam_rec(lat, lon, rkm*1000, hd, tl, vf), t=0.0)}, open(sys.argv[2], "w"), indent=1)
