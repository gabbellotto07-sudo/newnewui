"""Blender scene for the Seliu opening (run inside Blender, headless):
  blender -b -P tools/bl_scene.py -- CAMS.json OUTDIR [--w 1920 --h 1080 --spp 96 --clouds 1 --t T]

Terrain: Seliu level (L2, 64x64 km) as a real-sphere mesh with Copernicus GLO-30 relief, Sentinel-2 albedo.
Light: sun of the hero scene (29-07-2019, az 47, el 57) + sky. Clouds: the real cloud mask of the same day,
volumetric, ~650 m base (shadow-derived height 850 m = mean of the layer), drifting with the monsoon wind.
Writes multilayer EXR (Combined + Depth) per camera key: OUTDIR/<key>.exr
"""
import bpy, sys, os, json, math, time, numpy as np
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--")+1:]
cams_path, outdir = argv[0], argv[1]
def opt(k, d, f=float):
    return f(argv[argv.index(k)+1]) if k in argv else d
W, H = opt("--w", 1920, int), opt("--h", 1080, int)
SPP = opt("--spp", 96, int); CLOUDS = opt("--clouds", 1, int); TSHIFT = opt("--t", None)
PREFIX = argv[argv.index("--prefix")+1] if "--prefix" in argv else "L2"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda *p: os.path.join(ROOT, "data", *p)
SUN_AZ, SUN_EL = 46.0, 57.5
WIND = (-6.0, 4.0)
os.makedirs(outdir, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

# ---------------------------------------------------------------- terrain mesh
t0 = time.time()
V = np.load(D("bl", f"{PREFIX}_verts.npy")); UV = np.load(D("bl", f"{PREFIX}_uv.npy")); n = V.shape[0]
META = json.load(open(D("bl", f"{PREFIX}_meta.json"))) if os.path.exists(D("bl", f"{PREFIX}_meta.json")) else {"cx": 0, "cy": 0, "half": 32000, "base": 720.0, "dome_max": 420.0}
me = bpy.data.meshes.new("L2")
me.vertices.add(n*n); me.vertices.foreach_set("co", V.reshape(-1))
i = np.arange(n*n).reshape(n, n)
q = np.stack([i[1:, :-1], i[1:, 1:], i[:-1, 1:], i[:-1, :-1]], -1).reshape(-1)   # CCW seen from above (rows go south)
nf = (n-1)*(n-1)
me.loops.add(nf*4); me.loops.foreach_set("vertex_index", q.astype(np.int32))
me.polygons.add(nf); me.polygons.foreach_set("loop_start", np.arange(0, nf*4, 4, dtype=np.int32))
me.polygons.foreach_set("use_smooth", np.ones(nf, bool))
uvl = me.uv_layers.new(name="UV"); uvl.data.foreach_set("uv", UV.reshape(-1, 2)[q].reshape(-1))
me.update(calc_edges=True); me.validate()
ob = bpy.data.objects.new("L2", me); sc.collection.objects.link(ob)
print("mesh", n, "x", n, "%.1fs" % (time.time()-t0), flush=True)

def np_image(name, arr, channels):
    h, w = arr.shape[:2]
    img = bpy.data.images.new(name, w, h, alpha=True, float_buffer=True)
    img.colorspace_settings.name = "Non-Color"
    if channels == 1: arr = np.repeat(arr[..., None], 4, -1)
    img.pixels.foreach_set(np.ascontiguousarray(arr, np.float32).reshape(-1))
    img.pack()
    return img

alb = np_image("albedo", np.load(D("bl", f"{PREFIX}_albedo.npy")), 4)
mat = bpy.data.materials.new("ground"); mat.use_nodes = True
nt = mat.node_tree; N = nt.nodes; L = nt.links; N.clear()
out = N.new("ShaderNodeOutputMaterial")
tex = N.new("ShaderNodeTexImage"); tex.image = alb; tex.interpolation = "Cubic"; tex.extension = "EXTEND"
uvn = N.new("ShaderNodeUVMap"); uvn.uv_map = "UV"; L.new(uvn.outputs[0], tex.inputs[0])
bl = N.new("ShaderNodeBsdfPrincipled")      # land: matte
bw = N.new("ShaderNodeBsdfPrincipled")      # water: same albedo, faint specular sheen (Fresnel toward the horizon)
for b, r, s in ((bl, 0.95, 0.15), (bw, 0.12, 0.6)):
    L.new(tex.outputs["Color"], b.inputs["Base Color"]); b.inputs["Roughness"].default_value = r
    b.inputs["Specular IOR Level"].default_value = s
bw.inputs["IOR"].default_value = 1.333
mix = N.new("ShaderNodeMixShader"); L.new(tex.outputs["Alpha"], mix.inputs[0])
L.new(bw.outputs[0], mix.inputs[1]); L.new(bl.outputs[0], mix.inputs[2]); L.new(mix.outputs[0], out.inputs["Surface"])
me.materials.append(mat)

# ---------------------------------------------------------------- sun + sky
sd = Vector((math.sin(math.radians(SUN_AZ))*math.cos(math.radians(SUN_EL)),
             math.cos(math.radians(SUN_AZ))*math.cos(math.radians(SUN_EL)), math.sin(math.radians(SUN_EL))))
sun = bpy.data.lights.new("sun", "SUN"); sun.energy = 4.0; sun.angle = math.radians(0.53)
so = bpy.data.objects.new("sun", sun); sc.collection.objects.link(so)
so.rotation_euler = (-sd).to_track_quat("-Z", "Y").to_euler()
wd = bpy.data.worlds.new("w"); sc.world = wd; wd.use_nodes = True
wn = wd.node_tree.nodes; wn.clear()
sky = wn.new("ShaderNodeTexSky"); sky.sky_type = "NISHITA"; sky.sun_disc = False
sky.sun_elevation = math.radians(SUN_EL); sky.sun_rotation = math.radians(90-SUN_AZ)
sky.altitude = 1000; sky.air_density = 1.0; sky.dust_density = 2.0
bg = wn.new("ShaderNodeBackground"); bg.inputs[1].default_value = 0.03   # Nishita is in physical units; sun lamp is 4
wo = wn.new("ShaderNodeOutputWorld")
wd.node_tree.links.new(sky.outputs[0], bg.inputs[0]); wd.node_tree.links.new(bg.outputs[0], wo.inputs[0])

# ---------------------------------------------------------------- real clouds, volumetric
if CLOUDS:
    cl = np_image("cloud", np.load(D("bl", f"{PREFIX}_cloud.npy")), 1)
    BASE, TOP = META["base"], META["base"]+META["dome_max"]
    bpy.ops.mesh.primitive_cube_add(size=1)
    cb = bpy.context.active_object; cb.name = "clouds"
    cb.scale = (2*META["half"], 2*META["half"], TOP-BASE); cb.location = (META["cx"], META["cy"], (BASE+TOP)/2)
    cm = bpy.data.materials.new("cloud"); cm.use_nodes = True
    T_ = cm.node_tree; n_ = T_.nodes; l_ = T_.links; n_.clear()
    o = n_.new("ShaderNodeOutputMaterial")
    tc = n_.new("ShaderNodeTexCoord")
    sep = n_.new("ShaderNodeSeparateXYZ"); l_.new(tc.outputs["Object"], sep.inputs[0])
    # object coords: x,y in -0.5..0.5 of 64 km, z -0.5..0.5 of the layer
    def math_node(op, a=None, b=None, va=None, vb=None):
        m = n_.new("ShaderNodeMath"); m.operation = op
        if a is not None: l_.new(a, m.inputs[0])
        else: m.inputs[0].default_value = va
        if b is not None: l_.new(b, m.inputs[1])
        elif vb is not None: m.inputs[1].default_value = vb
        return m
    shift = n_.new("ShaderNodeValue"); shift.name = "wind_t"; shift.outputs[0].default_value = 0.0
    ux = math_node("ADD", sep.outputs[0], None, vb=0.5)
    wx = math_node("MULTIPLY", shift.outputs[0], None, vb=-WIND[0]/(2*META["half"]))
    ux2 = math_node("ADD", ux.outputs[0], wx.outputs[0])
    uy = math_node("ADD", sep.outputs[1], None, vb=0.5)
    wy = math_node("MULTIPLY", shift.outputs[0], None, vb=-WIND[1]/(2*META["half"]))
    uy2 = math_node("ADD", uy.outputs[0], wy.outputs[0])
    cmb = n_.new("ShaderNodeCombineXYZ"); l_.new(ux2.outputs[0], cmb.inputs[0]); l_.new(uy2.outputs[0], cmb.inputs[1])
    # small domain warp so the 10 m mask edges become billowy, not pixel blobs
    nz = n_.new("ShaderNodeTexNoise"); nz.noise_dimensions = "3D"; nz.inputs["Scale"].default_value = 900.0
    nz.inputs["Detail"].default_value = 6.0; nz.inputs["Roughness"].default_value = 0.62
    l_.new(tc.outputs["Object"], nz.inputs["Vector"])
    wn_ = n_.new("ShaderNodeVectorMath"); wn_.operation = "SUBTRACT"; l_.new(nz.outputs["Color"], wn_.inputs[0]); wn_.inputs[1].default_value = (0.5, 0.5, 0.5)
    ws = n_.new("ShaderNodeVectorMath"); ws.operation = "SCALE"; l_.new(wn_.outputs[0], ws.inputs[0]); ws.inputs[3].default_value = 0.7e-3
    wsum = n_.new("ShaderNodeVectorMath"); wsum.operation = "ADD"; l_.new(cmb.outputs[0], wsum.inputs[0]); l_.new(ws.outputs[0], wsum.inputs[1])
    ct = n_.new("ShaderNodeTexImage"); ct.image = cl; ct.interpolation = "Cubic"; ct.extension = "CLIP"
    l_.new(wsum.outputs[0], ct.inputs[0])
    # dome profile: height above base (m) must be below the local top = thick * a^0.6 * (1 + detail)
    zm = math_node("ADD", sep.outputs[2], None, vb=0.5); zm = math_node("MULTIPLY", zm.outputs[0], None, vb=TOP-BASE)
    det = math_node("MULTIPLY", nz.outputs["Fac"], None, vb=0.8); det = math_node("ADD", det.outputs[0], None, vb=0.6)
    top = math_node("MULTIPLY", ct.outputs["Color"], det.outputs[0])
    inside = math_node("SUBTRACT", top.outputs[0], zm.outputs[0])
    soft = math_node("DIVIDE", inside.outputs[0], None, vb=25.0); soft.use_clamp = True
    floor_ = math_node("DIVIDE", zm.outputs[0], None, vb=30.0); floor_.use_clamp = True     # flat-ish bases
    dens = math_node("MULTIPLY", soft.outputs[0], floor_.outputs[0])
    dens = math_node("MULTIPLY", dens.outputs[0], None, vb=0.08)
    pv = n_.new("ShaderNodeVolumePrincipled"); pv.inputs["Color"].default_value = (1, 1, 1, 1)
    pv.inputs["Anisotropy"].default_value = 0.55
    l_.new(dens.outputs[0], pv.inputs["Density"]); l_.new(pv.outputs[0], o.inputs["Volume"])
    cb.data.materials.append(cm)

# ---------------------------------------------------------------- render settings
sc.render.engine = "CYCLES"; cy = sc.cycles
cy.device = "CPU"; cy.samples = SPP; cy.use_adaptive_sampling = True; cy.adaptive_threshold = 0.02
cy.use_denoising = True; cy.denoiser = "OPENIMAGEDENOISE"
cy.max_bounces = 6; cy.diffuse_bounces = 2; cy.glossy_bounces = 1; cy.volume_bounces = 2; cy.transmission_bounces = 0
cy.volume_step_rate = 2.0; cy.volume_max_steps = 256
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
sc.render.threads_mode = "AUTO"
sc.view_settings.view_transform = "Standard"; sc.view_settings.look = "None"
sc.render.image_settings.file_format = "OPEN_EXR_MULTILAYER"; sc.render.image_settings.color_depth = "16"
sc.view_layers[0].use_pass_z = True
cam = bpy.data.cameras.new("cam"); cam.sensor_fit = "VERTICAL"; cam.clip_start = 50; cam.clip_end = 400000
co = bpy.data.objects.new("cam", cam); sc.collection.objects.link(co); sc.camera = co

cams = json.load(open(cams_path))
for key, c in cams.items():
    f, u = Vector(c["fwd"]), Vector(c["up"]); r = f.cross(u)
    M = Matrix((r, u, -f)).transposed()
    co.matrix_world = Matrix.Translation(Vector(c["pos"])) @ M.to_4x4()
    cam.angle_y = math.radians(c["vfov"])
    if CLOUDS: bpy.data.materials["cloud"].node_tree.nodes["wind_t"].outputs[0].default_value = c["t"] if TSHIFT is None else TSHIFT
    sc.render.filepath = os.path.join(outdir, f"{key}.exr")
    t1 = time.time(); bpy.ops.render.render(write_still=True)
    print(f"RENDERED {key} alt={c['alt']:.0f}m {time.time()-t1:.1f}s", flush=True)
