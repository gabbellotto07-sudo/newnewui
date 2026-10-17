"""v8 timing for the motion graphics (same design as v6, docs/05-direzione-grafica.md), on the 28 s flight.
Only the timing chart changes; every gesture, size and colour is motion_gfx's. Retime here.
    draw(img, t, cam, fmt)  -> motion_gfx.draw with the v8 camera for screen-velocity motion blur"""
import motion_gfx as M
import timeline_v8 as TL

M.T.update(
    region_in=3.0,
    sin_dot=3.55, sin_label=3.70, cgk_dot=4.05, cgk_label=4.20,
    arc_sin=(5.00, 7.80), arc_cgk=(5.45, 8.25),
    flights_note=6.10, tjq_arrive=7.80,
    bel_small=8.35, region_out=(8.90, 10.0),
    bel_title=10.70, bel_rule=11.20, bel_sub=11.45, bel_out=13.45, bel_ref=12.0,
    outline=(18.10, 20.50), outline_flash=20.50,
    seliu_title=18.70, seliu_sub=19.50, seliu_ref=25.0,
    tg_dot=20.70, tg_label=20.85, tg_ref=27.9,
    route=(21.30, 23.80), boat_note=22.30, jetty=23.80,
    glint=(23.90, 26.10),
)
T = M.T

# sound touches for the graphics (read by sound_v8.gfx_layer): real paper / air, far under the ambience
SOUND_CUES = [
    dict(t=T["sin_dot"], kind="dot", db=-38, pan=-0.45), dict(t=T["cgk_dot"], kind="dot", db=-38, pan=-0.30),
    dict(t=T["tjq_arrive"], kind="dot", db=-37, pan=0.15),
    dict(t=T["bel_title"]-0.05, kind="title", db=-31, pan=0.0),
    dict(t=T["seliu_title"]-0.05, kind="title", db=-30, pan=-0.1),
    dict(t=T["tg_dot"], kind="dot", db=-37, pan=0.55),
    dict(t=T["jetty"], kind="dot", db=-36, pan=-0.25),
]
M.SOUND_CUES = SOUND_CUES

def draw(img, t, cam, fmt="16x9"):
    import render_v8 as R
    H, W = img.shape[:2]
    return M.draw(img, t, cam, fmt=fmt, cam_at=lambda tt: R.cam_at(tt, cam.W, cam.H))
