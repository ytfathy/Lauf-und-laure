# Run with Malek - Malek character, Pixar-style, built procedurally in Blender.
# Usage: blender -b --factory-startup -P malek.py -- <out_dir> [render]
# Coordinates: Blender Z-up, character faces -Y. Joint heights match the game rig (gc):
#   pelvis .66, torso .72, head 1.22, shoulders (+-.27, 1.12), elbows .87, hips (+-.11, .62), knees .34
import bpy, bmesh, math, sys, os, random
from mathutils import Vector, Euler, Matrix

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = argv[0] if argv else os.getcwd()
DO_RENDER = len(argv) > 1 and argv[1] in ('render', 'quick')
QUICK = len(argv) > 1 and argv[1] == 'quick'
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
SC = bpy.context.scene
K = 1 / 0.5749            # metaball radius -> surface radius at stiffness 2 (calibrated)
P = math.pi

# ---------------- palette (Character Sheet 02) ----------------
C = dict(skin=0xf1bd92, hair=0x4a2a17, jacket=0x1f3fa0, accent=0xf4f4f4, shirt=0xf7f7f7, hood=0xd5dae4,
         shorts=0x3a3f4a, sock=0xffffff, shoe=0xffffff, shoeAccent=0x1f5fd0, sole=0xf2f2f2,
         bag=0xc9802b, letter=0xf6c21b, phones=0xf4f4f4, iris=0x6b3a1a)

def lin(h):
    c = [((h >> s) & 255) / 255 for s in (16, 8, 0)]
    return tuple(x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4 for x in c)

MATS = {}
def mat(name, hexc, rough=.6, sss=0., sheen=0., coat=0., emit=0., alpha=1.):
    if name in MATS: return MATS[name]
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']; I = b.inputs
    I['Base Color'].default_value = (*lin(hexc), 1); I['Roughness'].default_value = rough
    if sss:
        I['Subsurface Weight'].default_value = sss; I['Subsurface Radius'].default_value = (1., .4, .25); I['Subsurface Scale'].default_value = .02
    if sheen: I['Sheen Weight'].default_value = sheen; I['Sheen Roughness'].default_value = .5
    if coat: I['Coat Weight'].default_value = coat; I['Coat Roughness'].default_value = .15
    if emit: I['Emission Color'].default_value = (*lin(hexc), 1); I['Emission Strength'].default_value = emit
    if alpha < 1: I['Alpha'].default_value = alpha
    MATS[name] = m; return m

M_SKIN = mat('skin', C['skin'], .45, sss=.25)
M_SKIN_D = mat('skinDark', 0xd99a78, .5, sss=.2)
M_HAIR = mat('hair', C['hair'], .55, sheen=.35, coat=.05)
M_JACKET = mat('jacket', C['jacket'], .75, sheen=.5)
M_JACKET_D = mat('jacketDark', 0x172f78, .75, sheen=.4)
M_ACCENT = mat('accent', C['accent'], .8, sheen=.4)
M_SHIRT = mat('shirt', C['shirt'], .85, sheen=.4)
M_HOOD = mat('hood', C['hood'], .85, sheen=.5)
M_SHORTS = mat('shorts', C['shorts'], .8, sheen=.3)
M_SHORTS_D = mat('shortsDark', 0x2b2f38, .8)
M_SOCK = mat('sock', C['sock'], .9, sheen=.3)
M_SHOE = mat('shoe', C['shoe'], .35, coat=.4)
M_SHOE_A = mat('shoeAccent', C['shoeAccent'], .35, coat=.4)
M_SOLE = mat('sole', C['sole'], .6)
M_BAG = mat('bag', C['bag'], .7, sheen=.3)
M_BAG_D = mat('bagDark', 0x9a5f1f, .7)
M_LETTER = mat('letter', C['letter'], .5, coat=.3)
M_PHONES = mat('phones', C['phones'], .25, coat=.6)
M_PHONES_D = mat('phonesDark', 0x2a2a2e, .7)
M_EYE = mat('eyeWhite', 0xffffff, .08, coat=1.)
M_IRIS = mat('iris', C['iris'], .15, coat=1.)
M_PUPIL = mat('pupil', 0x0a0604, .1, coat=1.)
M_HL = mat('highlight', 0xffffff, .1, emit=3.)
M_MOUTH = mat('mouth', 0x4a1218, .7)
M_TEETH = mat('teeth', 0xfbfaf5, .25, coat=.5)
M_TONGUE = mat('tongue', 0xe0607a, .45, sss=.2)
M_BROW = mat('brow', 0x3a2010, .6)
M_BLUSH = mat('blush', 0xf4a49a, .55, sss=.2)

PARTS = []   # (object, bone) for the later game export
def link(ob, bone):
    SC.collection.objects.link(ob); ob['bone'] = bone; PARTS.append(ob); return ob

def smooth(me):
    for p in me.polygons: p.use_smooth = True

def bake(ob):
    """Replace an object (metaball/curve/text/modified mesh) by a plain mesh object."""
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    name, bone, mats, mw = ob.name, ob.get('bone'), [s.material for s in ob.material_slots], ob.matrix_world.copy()
    if ob in PARTS: PARTS.remove(ob)
    bpy.data.objects.remove(ob)
    me.materials.clear()
    for m in mats: me.materials.append(m)
    o = bpy.data.objects.new(name, me); o.matrix_world = mw; smooth(me)
    return link(o, bone)

def meta(name, bone, material, elems, res=.007, thr=.6):
    """elems: dicts with t(ype), co, r (surface radius), s(tiffness), size, rot, neg"""
    mb = bpy.data.metaballs.new(name); mb.resolution = res; mb.render_resolution = res; mb.threshold = thr
    ob = bpy.data.objects.new(name, mb)
    for e in elems:
        el = mb.elements.new(); el.type = e.get('t', 'BALL'); el.co = e['co']
        s = e.get('s', 2.)
        el.stiffness = s; el.radius = e['r'] * {1.: 1 / .3956, 1.5: 1 / .5130, 2.: K, 3.: 1 / .6443}.get(s, K)
        if 'size' in e: el.size_x, el.size_y, el.size_z = e['size']
        if 'rot' in e: el.rotation = Euler(e['rot']).to_quaternion()
        if e.get('neg'): el.use_negative = True
    ob.data.materials.append(material)
    link(ob, bone)
    return bake(ob)

def prim(kind, name, bone, material, loc, scale=(1, 1, 1), rot=(0, 0, 0), **kw):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    if kind == 'sphere': bmesh.ops.create_uvsphere(bm, u_segments=kw.get('u', 32), v_segments=kw.get('v', 16), radius=1)
    elif kind == 'cyl': bmesh.ops.create_cone(bm, cap_ends=True, segments=kw.get('seg', 32), radius1=1, radius2=kw.get('top', 1), depth=1)
    elif kind == 'cube': bmesh.ops.create_cube(bm, size=1)
    elif kind == 'torus':
        R, r = kw.get('R', 1), kw.get('r', .2)
        bm.free(); bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=r, major_segments=48, minor_segments=12)
        t = bpy.context.active_object; t.name = name
        t.location, t.scale, t.rotation_euler = loc, scale, rot
        for s in list(t.users_collection): s.objects.unlink(t)
        t.data.materials.append(material); smooth(t.data); return link(t, bone)
    bm.to_mesh(me); bm.free(); smooth(me); me.materials.append(material)
    ob = bpy.data.objects.new(name, me); ob.location, ob.scale, ob.rotation_euler = loc, scale, rot
    link(ob, bone)
    if kw.get('bevel'):
        b = ob.modifiers.new('bev', 'BEVEL'); b.width = kw['bevel']; b.segments = 4; b.limit_method = 'NONE'
        ob.modifiers.new('sub', 'SUBSURF').levels = 2
        ob = bake(ob)
    return ob

def tube(name, bone, material, pts, r, res=4):
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = r; cu.bevel_resolution = 4; cu.resolution_u = 12
    cu.use_fill_caps = True
    sp = cu.splines.new('BEZIER'); sp.bezier_points.add(len(pts) - 1)
    for bp, p in zip(sp.bezier_points, pts): bp.co = p; bp.handle_left_type = bp.handle_right_type = 'AUTO'
    ob = bpy.data.objects.new(name, cu); cu.materials.append(material); link(ob, bone)
    return bake(ob)

def cap(name, bone, material, loc, radius, angle, axis, r_scale=1.):
    """Spherical cap (iris / pupil / eyelid) of `radius` around `axis`, opening `angle` rad."""
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=64, radius=radius)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z / radius < math.cos(angle) - 1e-4], context='VERTS')
    q = Vector((0, 0, 1)).rotation_difference(Vector(axis).normalized())
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=q.to_matrix())
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); smooth(me); me.materials.append(material)
    ob = bpy.data.objects.new(name, me); ob.location = loc; ob.scale = (r_scale,) * 3
    return link(ob, bone)

def boolean(target, cutter, op='DIFFERENCE'):
    m = target.modifiers.new('bool', 'BOOLEAN'); m.object = cutter; m.operation = op; m.solver = 'EXACT'
    nb = bake(target)
    if cutter in PARTS: PARTS.remove(cutter)
    bpy.data.objects.remove(cutter)
    return nb

# ======================= HEAD (bone: head) =======================
HC = Vector((0, 0, 1.54))     # cranium centre
head = meta('head', 'head', M_SKIN, [
    dict(t='ELLIPSOID', co=HC, r=.31, size=(1, .97, 1.03)),
    dict(t='ELLIPSOID', co=(0, -.05, 1.41), r=.24, size=(1.02, .86, .9)),          # jaw / cheeks mass
    dict(co=(0, -.15, 1.33), r=.085, s=1.5),                                        # chin
    dict(co=(-.135, -.17, 1.445), r=.105, s=1.5), dict(co=(.135, -.17, 1.445), r=.105, s=1.5),   # cheeks (lifted by the smile)
    dict(co=(0, -.29, 1.45), r=.03, s=2.),                                       # nose
    dict(t='ELLIPSOID', co=(-.3, .0, 1.48), r=.065, size=(.6, .8, 1.15), s=1.5),    # ears
    dict(t='ELLIPSOID', co=(.3, .0, 1.48), r=.065, size=(.6, .8, 1.15), s=1.5),
])
from mathutils.bvhtree import BVHTree
_bvh = BVHTree.FromObject(head, bpy.context.evaluated_depsgraph_get())
def surf(x, z):
    hit = _bvh.ray_cast(Vector((x, -2, z)), Vector((0, 1, 0)))[0]
    return hit.y if hit else -.28
print('SURF eye', surf(.108, 1.535), 'mouth', surf(0, 1.36), 'brow', surf(.11, 1.68))
def tube2(name, bone, material, pts, r, radii):
    """Tapered tube: bezier through pts, per-point radius multipliers."""
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = r; cu.bevel_resolution = 3; cu.resolution_u = 8
    cu.use_fill_caps = True
    sp = cu.splines.new('BEZIER'); sp.bezier_points.add(len(pts) - 1)
    for bp, p, k in zip(sp.bezier_points, pts, radii):
        bp.co = p; bp.radius = k; bp.handle_left_type = bp.handle_right_type = 'AUTO'
    ob = bpy.data.objects.new(name, cu); cu.materials.append(material); link(ob, bone)
    return bake(ob)

# ---- closed, natural smile: a soft engraved curve with upturned corners (no lips, no teeth) ----
def smile_pts(off, n=13, w=.072, depth=.026, z0=1.372):
    pts = []
    for i in range(n):
        x = -w + 2 * w * i / (n - 1)
        z = z0 - depth * (1 - (x / w) ** 2)
        pts.append(Vector((x, surf(x, z) + off, z)))
    return pts
groove = tube2('smileCut', 'head', M_MOUTH, smile_pts(.0), .008, [.7] + [1] * 11 + [.7])
head = boolean(head, groove)                                   # shallow crease in the skin
tube2('smile', 'head', M_MOUTH, smile_pts(.005), .0055, [.35] + [1] * 11 + [.35])
for s in (-1, 1):   # little upturned corner creases
    x0, z0 = s * .072, 1.372
    tube2('smileCorner', 'head', M_MOUTH, [Vector((x0, surf(x0, z0) + .006, z0)),
          Vector((x0 + s * .01, surf(x0 + s * .01, z0 + .012) + .006, z0 + .012))], .005, [.8, .2])
for s in (-1, 1):   # inner ears
    prim('sphere', 'earIn', 'head', M_SKIN_D, (s * .312, -.025, 1.48), (.018, .03, .045))

# ---- eyes: big glossy eyes, layered iris, lash line, outer-corner flicks ----
ER = .096
M_IRIS_RIM = mat('irisRim', 0x2e150a, .15, coat=1.)
M_LINER = mat('liner', 0x1e1008, .5)
LID_A = Vector((0, math.sin(.62), math.cos(.62))); LID_ANG = math.radians(74)
for s in (-1, 1):
    c = Vector((s * .112, surf(s * .112, 1.54) + ER - .018, 1.54))
    prim('sphere', 'eye', 'head', M_EYE, c, (ER, ER, ER))
    look = Vector((0, -1, .02))
    cap('irisRim', 'head', M_IRIS_RIM, c, ER * 1.004, .72, look)
    cap('iris', 'head', M_IRIS, c, ER * 1.007, .64, look)
    cap('pupil', 'head', M_PUPIL, c, ER * 1.011, .3, look)
    cap('lid', 'head', M_SKIN, c, ER * 1.075, LID_ANG, LID_A)
    # lash line along the front of the lid edge, thicker towards the outer corner
    u = Vector((1, 0, 0)); v = LID_A.cross(u)
    ring = []
    for k in range(40):
        ph = 2 * P * k / 40
        d = math.cos(LID_ANG) * LID_A + math.sin(LID_ANG) * (math.cos(ph) * u + math.sin(ph) * v)
        if d.y < -.25: ring.append(c + d * ER * 1.09)
    ring.sort(key=lambda p: s * p.x)                   # inner corner -> outer corner
    pl = ring[::2] if (len(ring) - 1) % 2 == 0 else ring[::2] + [ring[-1]]     # no duplicate end point
    tube2('liner', 'head', M_LINER, pl, .009, [.6 + .8 * i / max(1, len(pl) - 1) for i in range(len(pl))])
    prim('sphere', 'hl', 'head', M_HL, c + Vector((s * .02 + .014, -ER * .88, .036)), (.02,) * 3)
    prim('sphere', 'hl2', 'head', M_HL, c + Vector((-.02, -ER * .95, -.026)), (.009,) * 3)
    # thick arched brows, raised (happy)
    tube2('brow', 'head', M_BROW, [(s * x, surf(s * x, z) - .006, z) for x, z in ((.04, 1.685), (.085, 1.712), (.135, 1.722), (.18, 1.705))], .02, [.9, 1, .85, .45])

# ---- hair: skull cap + tapered swept curly locks + a side-swept fringe ----
rng = random.Random(7)
hair = [dict(t='ELLIPSOID', co=(0, .03, 1.58), r=.325, size=(1, 1, 1.0), s=2.),
        dict(t='ELLIPSOID', co=(0, -.33, 1.43), r=.27, size=(1.2, 1, 1.15), neg=True, s=2.),      # face clearance
        dict(t='ELLIPSOID', co=(0, -.12, 1.22), r=.26, size=(1.3, 1.2, .7), neg=True, s=2.)]        # nape / neck clearance
meta('hair', 'head', M_HAIR, hair, res=.008)
HO = HC + Vector((0, .02, .04))
crown = Vector((0, .25, 1)).normalized()
n, gold = 190, P * (3 - math.sqrt(5))
for i in range(n):
    z = 1 - i / (n - 1) * 2; rad = math.sqrt(1 - z * z); th = gold * i
    d = Vector((math.cos(th) * rad, math.sin(th) * rad, z))
    if d.z < (-.4 if d.y > .15 else -.08): continue
    if d.y < -.2 and d.z < .5 and abs(d.x) < .85: continue          # keep the face clear
    if d.z < .05 and abs(d.x) > .5 and d.y < .2: continue          # nothing dangling by the jaw
    t = (d - crown); t = t - d * t.dot(d)
    t = t.normalized() if t.length > 1e-3 else Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), 0)).normalized()
    side = d.cross(t); sg = 1 if i % 2 else -1
    L = .07 + rng.random() * .045; R = .05 + rng.random() * .02
    g = Vector((0, 0, -.035)) if d.z < .55 else Vector((0, 0, 0))
    root = HO + d * .29
    pts = [root,
           root + d * .065 + t * L * .5 + g * .4,
           root + d * .1 + t * L * .8 + side * sg * .04 + g,
           root + d * .08 + t * L * .45 + side * sg * .085 + g,
           root + d * .045 + t * L * .3 + side * sg * .06]                    # tip curls back towards the root
    tube2('lock', 'head', M_HAIR, pts, R, [1, 1, .85, .55, .2])
# fringe swept across the forehead to his right
for k in range(7):
    x0 = -.12 + k * .045
    pts = [(x0, -.12, 1.84), (x0 - .03, -.26, 1.82), (x0 - .07, -.31, 1.75), (x0 - .1, -.29, 1.69 + rng.random() * .02)]
    tube2('fringe', 'head', M_HAIR, [Vector(p) for p in pts], .045 + rng.random() * .01, [1, .9, .6, .2])

# ======================= TORSO (bone: torso) =======================
jacket = meta('jacket', 'torso', M_JACKET, [
    dict(t='ELLIPSOID', co=(0, 0, .95), r=.22, size=(1, .74, 1.12)),
    dict(t='ELLIPSOID', co=(0, -.005, .8), r=.205, size=(1, .78, .7)),
    dict(co=(-.2, 0, 1.1), r=.1), dict(co=(.2, 0, 1.1), r=.1),
])
# open front: slot through the jacket, white tee behind it
slot = prim('cube', 'slot', 'torso', M_JACKET, (0, -.2, .93), (.13, .2, .5))
jacket = boolean(jacket, slot)
meta('tee', 'torso', M_SHIRT, [dict(t='ELLIPSOID', co=(0, .005, .94), r=.205, size=(1, .74, 1.12)),
                               dict(t='ELLIPSOID', co=(0, 0, .8), r=.19, size=(1, .78, .7))])
for s in (-1, 1):   # lapel ridges along the opening
    tube('lapel', 'torso', M_JACKET_D, [(s * .066, -.168, .72), (s * .066, -.178, .9), (s * .07, -.16, 1.08), (s * .06, -.12, 1.15)], .012)
prim('torus', 'hem', 'torso', M_ACCENT, (0, 0, .72), (1, .76, 1), R=.205, r=.028)
prim('torus', 'hemStripe', 'torso', M_JACKET, (0, 0, .755), (1, .76, 1), R=.214, r=.009)
meta('hood', 'torso', M_HOOD, [dict(t='ELLIPSOID', co=(0, .02, 1.16), r=.13, size=(1.2, 1, .5)),
                               dict(t='ELLIPSOID', co=(0, .14, 1.14), r=.12, size=(1.2, .7, .8))])
prim('cyl', 'neck', 'torso', M_SKIN, (0, 0, 1.2), (.06, .06, .14))
# varsity "M" patch on the wearer's left chest
cu = bpy.data.curves.new('M', 'FONT'); cu.body = 'M'; cu.size = .085; cu.extrude = .006; cu.bevel_depth = .002; cu.align_x = 'CENTER'
t = bpy.data.objects.new('letter', cu); t.location = (.115, -.172, .99); t.rotation_euler = (P / 2, 0, math.radians(18))
cu.materials.append(M_LETTER); link(t, 'torso'); bake(t)
prim('cube', 'patch', 'torso', M_JACKET_D, (.112, -.165, 1.02), (.075, .01, .075), (0, 0, math.radians(18)), bevel=.008)
# headphones resting round the neck
prim('torus', 'phonesBand', 'torso', M_PHONES, (0, -.03, 1.2), (1.15, 1, 1), (math.radians(-20), 0, 0), R=.13, r=.02)
for s in (-1, 1):
    prim('cyl', 'cup', 'torso', M_PHONES, (s * .15, -.12, 1.17), (.055, .055, .04), (math.radians(70), 0, s * math.radians(35)))
    prim('cyl', 'cupPad', 'torso', M_PHONES_D, (s * .14, -.105, 1.18), (.045, .045, .042), (math.radians(70), 0, s * math.radians(35)))
# backpack + straps
prim('cube', 'bag', 'torso', M_BAG, (0, .24, .95), (.3, .15, .34), bevel=.065)
prim('cube', 'bagPocket', 'torso', M_BAG_D, (0, .325, .86), (.22, .05, .15), bevel=.02)
tube('zip', 'torso', M_PHONES_D, [(-.09, .352, .935), (0, .356, .938), (.09, .352, .935)], .004)
for s in (-1, 1):
    tube('strap', 'torso', M_BAG_D, [(s * .13, .17, 1.08), (s * .15, .06, 1.17), (s * .155, -.09, 1.13), (s * .155, -.165, 1.0), (s * .14, -.165, .8)], .017)

# ======================= PELVIS (bone: body) =======================
meta('shortsTop', 'body', M_SHORTS, [dict(t='ELLIPSOID', co=(0, 0, .67), r=.2, size=(1, .76, .55))])

# ======================= ARMS =======================
for s, side in ((-1, 'L'), (1, 'R')):
    x = s * .27
    meta('sleeve' + side, 'arm' + side, M_JACKET, [dict(co=(x, 0, 1.115), r=.088),
         dict(t='CAPSULE', co=(x, 0, 1.0), r=.07, size=(.1, 1, 1), rot=(0, P / 2, 0))])
    xf = s * .29
    meta('forearm' + side, 'fore' + side, M_JACKET, [dict(t='CAPSULE', co=(xf, 0, .77), r=.063, size=(.08, 1, 1), rot=(0, P / 2, 0))])
    for z in (.665, .69):
        prim('torus', 'cuff' + side, 'fore' + side, M_ACCENT, (xf, 0, z), (1, 1, 1), R=.062, r=.016)
    # mitten-style 4-finger hand
    h = [dict(t='ELLIPSOID', co=(xf, -.005, .6), r=.055, size=(.75, .6, 1)),
         dict(t='CAPSULE', co=(xf - s * .045, -.03, .61), r=.02, size=(.025, 1, 1), rot=(0, math.radians(60), s * .6))]
    for k, fx in enumerate((-.03, -.01, .01, .03)):
        h.append(dict(t='CAPSULE', co=(xf + fx, -.012, .54 + abs(fx) * .4), r=.018, size=(.022, 1, 1), rot=(0, P / 2 + .25, 0)))
    meta('hand' + side, 'fore' + side, M_SKIN, h, res=.005)

# ======================= LEGS =======================
for s, side in ((-1, 'L'), (1, 'R')):
    x = s * .11
    meta('thigh' + side, 'leg' + side, M_SHORTS, [dict(t='CAPSULE', co=(x, 0, .5), r=.092, size=(.09, 1, 1), rot=(0, P / 2, 0))])
    prim('torus', 'shortsHem' + side, 'leg' + side, M_SHORTS_D, (x, 0, .385), (1, 1, 1), R=.092, r=.014)
    meta('shin' + side, 'shin' + side, M_SKIN, [dict(t='CAPSULE', co=(x, 0, .27), r=.055, size=(.08, 1, 1), rot=(0, P / 2, 0))])
    prim('cyl', 'sock' + side, 'shin' + side, M_SOCK, (x, 0, .135), (.06, .06, .1))
    prim('torus', 'sockRib' + side, 'shin' + side, M_SOCK, (x, 0, .185), (1, 1, 1), R=.06, r=.012)
    # chunky sneaker
    meta('shoe' + side, 'shin' + side, M_SHOE, [
        dict(t='ELLIPSOID', co=(x, -.02, .075), r=.08, size=(.95, 1.8, .8)),
        dict(t='ELLIPSOID', co=(x, .07, .1), r=.07, size=(1, 1, 1)),
        dict(t='ELLIPSOID', co=(x, -.12, .06), r=.065, size=(1.1, 1.1, .75))], res=.005)
    meta('sole' + side, 'shin' + side, M_SOLE, [dict(t='ELLIPSOID', co=(x, -.025, .03), r=.09, size=(.95, 1.85, .32))], res=.005)
    tube('stripe' + side, 'shin' + side, M_SHOE_A, [(x + s * .078, .08, .07), (x + s * .083, -.0, .085), (x + s * .078, -.09, .06)], .012)
    tube('stripeIn' + side, 'shin' + side, M_SHOE_A, [(x - s * .078, .08, .07), (x - s * .083, -.0, .085), (x - s * .078, -.09, .06)], .012)
    prim('cube', 'heelTab' + side, 'shin' + side, M_SHOE_A, (x, .135, .12), (.05, .025, .07), bevel=.01)
    for k in range(3):
        prim('cube', 'lace' + side, 'shin' + side, M_SOCK, (x, -.06 + k * .035, .135 - k * .01), (.07, .012, .012), (math.radians(-20), 0, 0), bevel=.004)

# ======================= scene / render =======================
# per-bone collections make the later GLB export (and the .blend) easy to read
for ob in PARTS:
    name = 'bone_' + ob['bone']
    col = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if name not in SC.collection.children: SC.collection.children.link(col)
    for c in list(ob.users_collection): c.objects.unlink(ob)
    col.objects.link(ob)

tris = sum(len(o.data.polygons) for o in PARTS if o.type == 'MESH')
print('PARTS', len(PARTS), 'FACES', tris)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'malek.blend'))

if DO_RENDER:
    r = SC.render; r.engine = 'CYCLES'; SC.cycles.device = 'CPU'; SC.cycles.samples = 48; SC.cycles.use_denoising = True
    r.resolution_x, r.resolution_y = 900, 1100; r.film_transparent = False
    SC.view_settings.view_transform = 'AgX'; SC.view_settings.look = 'AgX - Punchy'
    w = bpy.data.worlds.new('w'); SC.world = w; w.use_nodes = True
    bg = w.node_tree.nodes['Background']; bg.inputs['Color'].default_value = (*lin(0x1d3c9e), 1); bg.inputs['Strength'].default_value = .6
    # ground disc
    bpy.ops.mesh.primitive_circle_add(vertices=64, radius=3, fill_type='NGON'); g = bpy.context.active_object
    g.data.materials.append(mat('ground', 0x2a4fc0, .8))
    def area(name, loc, power, size, color, target=(0, 0, .9)):
        L = bpy.data.lights.new(name, 'AREA'); L.energy = power; L.size = size; L.color = lin(color)
        o = bpy.data.objects.new(name, L); o.location = loc; SC.collection.objects.link(o)
        d = Vector(target) - Vector(loc); o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler(); return o
    area('key', (2.2, -3, 3.2), 520, 2.5, 0xfff0dc)
    area('fill', (-3, -2, 1.6), 140, 3, 0xcfe0ff)
    area('rim', (-1.5, 3, 2.8), 700, 2, 0xa8d4ff)
    area('rim2', (2.5, 2.5, 2), 350, 2, 0xffd6a8)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); SC.collection.objects.link(cam); SC.camera = cam
    cam.data.lens = 70
    def shoot(name, loc, target, lens=70, res=(900, 1100)):
        cam.location = loc; cam.data.lens = lens; r.resolution_x, r.resolution_y = res
        cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        r.filepath = os.path.join(OUT, name + '.png'); bpy.ops.render.render(write_still=True); print('RENDERED', name)
    shoot('malek-front', (1.3, -4.2, 1.35), (0, 0, .92))
    shoot('malek-face', (.55, -1.9, 1.55), (0, 0, 1.5), lens=85, res=(900, 900))
    if QUICK: sys.exit(0)
    shoot('malek-side', (4.4, -.4, 1.3), (0, 0, .92))
    shoot('malek-back', (-1.2, 4.3, 1.4), (0, 0, .92))
