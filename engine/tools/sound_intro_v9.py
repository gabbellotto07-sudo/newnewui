"""Seliu v9 — sound for the brand intro (5.6 s), joined to the flight's web mix. Restrained: no risers, no hits,
no trailer whoosh.
  air      real high air (Mixkit 1267), band 1.2-7 kHz, barely there under the logo; it carries over the cut and
           hands over to the flight's own orbit air in its first 1.5 s
  glass    a soft bowed-glass chord (C6 G6 C7, synthetic, slow attack) born with the rose; when the star launches it
           follows it: louder as it nears, a small Doppler (+0.4 then -1 semitone at the pass), panned with it
  turn     the camera's whip pan heard as air: real wind (Mixkit 1201), gain and brightness from the real angular
           speed of the turn, moving right -> left as the world does
usage: sound_intro_v9.py FLIGHT_WEB_MIX.wav OUT.wav [--tail_fade 0.6]"""
import sys, os, math, argparse, numpy as np, soundfile as sf
from scipy import signal
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sound_v9 as S
import intro_v9 as I
from scipy.spatial.transform import Rotation as Rot
SR = S.SR

def curves(n):
    """per-sample: angular speed of the camera (deg/s), star screen x (-1..1), star distance (u), star visible"""
    ts = np.arange(0, I.T0+0.04, 0.02)
    om, sx, dist = [], [], []
    for t in ts:
        a, b = I.basis(I.cam(t)), I.basis(I.cam(t+0.02))
        om.append(math.degrees(np.linalg.norm(Rot.from_matrix(b@a.T).as_rotvec()))/0.02)
        if t >= I.LAUNCH:
            c = I.cam(t); v, d = I.star3d(t); r = v@c.r; f = v@c.f
            sx.append(math.atan2(r, f)/(math.pi/2)); dist.append(d)
        else:
            sx.append(0.0); dist.append(60.0)
    tt = np.arange(n)/SR
    return (np.interp(tt, ts, om), np.clip(np.interp(tt, ts, sx), -1, 1), np.interp(tt, ts, dist))

def peak_rms(x, win=0.4):
    m = (x**2).mean(1); k = int(win*SR)
    return math.sqrt(max(np.convolve(m, np.ones(k)/k, "same").max(), 1e-14))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("flight"); ap.add_argument("out"); ap.add_argument("--tail_fade", type=float, default=0.6)
    a = ap.parse_args()
    fl, sr = sf.read(a.flight, always_2d=True); assert sr == SR
    n0 = int(round(I.T0*SR)); n = n0+len(fl)
    out = np.zeros((n, 2))
    ni = n0+int(1.6*SR)                                                   # the intro layers live to flight t=1.6
    om, sx, dist = curves(ni)
    t = np.arange(ni)/SR
    # air
    air = S.loop_to(S.load("mk_1267.wav", 3.0), ni)
    air = S.filt(S.filt(air, "highpass", 1200), "lowpass", 7000)
    e = S.env_pts(ni, [(0, 0), (0.6, 0.30), (3.0, 0.38), (4.4, 0.6), (5.0, 1.0), (I.T0+0.2, 1.0), (I.T0+1.6, 0.0)], 0.4)
    air = air*e[:, None]; out[:ni] += air/peak_rms(air)*S.db(-35)
    # glass: phase-accumulated so the Doppler bend is continuous
    semis = np.where(t < I.LAUNCH, 0.0, 0.4*np.clip((t-I.LAUNCH)/0.7, 0, 1))
    semis = semis-1.4*np.clip((t-(I.T_EXIT-0.06))/0.18, 0, 1)
    ratio = 2**(semis/12)
    g = np.zeros(ni)
    for f, amp in ((1046.5, 1.0), (1568.0, 0.55), (2093.0, 0.28)):
        ph = 2*np.pi*np.cumsum(f*ratio*(1+0.0008*np.sin(2*np.pi*0.7*t+f)))/SR
        g += amp*np.sin(ph)
    near = np.clip(12.0/np.maximum(dist, 1.0), 0, 1)
    ge = S.env_pts(ni, [(0, 0), (0.25, 0), (1.1, 0.30), (2.6, 0.26), (3.1, 0.30), (I.T_EXIT, 1.0), (I.T_EXIT+0.3, 0.0)], 0.12)
    ge = ge*(0.35+0.65*np.where(t >= I.LAUNCH, near, 0.0)/np.maximum(near.max(), 1e-6))*(t < I.T_EXIT+0.45)
    glass = np.stack([g, g], 1)*ge[:, None]
    glass = S.pan(glass, np.where(t >= I.LAUNCH, sx, 0.0)*0.8)
    glass = S.filt(glass, "lowpass", 5000)
    out[:ni] += glass/peak_rms(glass)*S.db(-28)
    # weight under the pass: a low swell of air (no hit), 35-110 Hz
    lo = S.filt(S.filt(S.loop_to(S.load("mk_1172.wav", 2.0), ni), "lowpass", 110, 4), "highpass", 35)
    le = S.env_pts(ni, [(0, 0), (I.T_EXIT-0.35, 0), (I.T_EXIT, 1.0), (I.T_EXIT+0.7, 0.25), (I.PAN1, 0)], 0.15)
    lo = lo*le[:, None]; out[:ni] += lo/peak_rms(lo)*S.db(-27)
    # turn
    wnd = S.loop_to(S.load("mk_1201.wav", 6.0), ni)
    k = np.clip(om/150.0, 0, 1)
    wnd = S.sweep(S.filt(wnd, "highpass", 500), "lowpass", 1500+4500*k)
    pp = np.clip(1-2*np.clip((t-I.PAN0)/(I.T0-I.PAN0), 0, 1), -0.7, 0.7)      # right -> left with the world
    turn = S.pan(wnd, pp)*(k**1.4)[:, None]
    out[:ni] += turn/peak_rms(turn)*S.db(-24)
    # the flight, with a soft tail
    tail = int(a.tail_fade*SR)
    fl = fl.copy(); fl[-tail:] *= np.cos(np.linspace(0, np.pi/2, tail))[:, None]**2
    out[n0:] += fl
    out = S.limit(out)
    sf.write(a.out, out.astype(np.float32), SR, subtype="PCM_24")
    import pyloudnorm as pyln
    m = pyln.Meter(SR)
    print("intro version", round(m.integrated_loudness(out), 1), "LUFS; intro only", round(m.integrated_loudness(out[:n0]), 1), "LUFS")

if __name__ == "__main__":
    main()
