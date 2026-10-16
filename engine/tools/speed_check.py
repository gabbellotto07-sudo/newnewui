"""On-screen speed along the flight (no render): median / max px per frame of ground points, every 0.2 s,
and the jumps between neighbours (a jerk shows as a sudden ratio). usage: speed_check.py OUT.json [W H]"""
import sys, os, json, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_v9 as R
W = int(sys.argv[2]) if len(sys.argv) > 2 else (1920 if R.TL.FMT == "16x9" else 1080)
H = int(sys.argv[3]) if len(sys.argv) > 3 else (1080 if R.TL.FMT == "16x9" else 1920)
ts = np.arange(0, R.TL.DURATION, 0.2)
med = []; mx = []
for t in ts:
    a, b = R.screen_speed(float(t), W, H); med.append(a); mx.append(b)
med = np.array(med); r = med[1:]/np.maximum(med[:-1], 1e-3)
jerks = [dict(t=round(float(ts[i+1]), 1), ratio=round(float(r[i]), 2)) for i in range(len(r)) if (r[i] > 1.35 or r[i] < 1/1.35) and max(med[i], med[i+1]) > 2.0]
out = dict(fmt=R.TL.FMT, px_per_frame_median={f"{t:.1f}": round(float(v), 2) for t, v in zip(ts, med)},
           max_px_per_frame=round(float(np.max(mx)), 1), slowest_after_1s=round(float(med[ts >= 1].min()), 2),
           last_second_median=round(float(med[ts >= 27].mean()), 2), sudden_changes=jerks)
json.dump(out, open(sys.argv[1], "w"), indent=1)
print(json.dumps({k: v for k, v in out.items() if k != "px_per_frame_median"}, indent=1))
