# Run with Malek - all playable characters, Pixar-style, built procedurally in Blender.
# Usage: blender -b --factory-startup -P chars.py -- <out_dir> [render|quick] [only_id]
# Blender Z-up, characters face -Y. Joint heights match the game rig (gc):
#   pelvis .66, torso .72, head 1.22, shoulders (+-.27, 1.12), elbows .87, hips (+-.11, .62), knees .34
import bpy, bmesh, math, sys, os, random
from mathutils import Vector, Euler
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else os.getcwd())
MODE = argv[1] if len(argv) > 1 else ''
ONLY = argv[2] if len(argv) > 2 else None
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
SC = bpy.context.scene
K = 1 / 0.5749            # metaball radius -> surface radius at stiffness 2 (calibrated)
STIFF = {1.: 1 / .3956, 1.5: 1 / .5130, 2.: K, 3.: 1 / .6443}
P = math.pi

# ---------------- characters (Character Sheet 02) ----------------
CHARS = [
    dict(id='malek', name='Malek', skin=0xf1bd92, hair=0x4a2a17, hairStyle='curly', top=0x1f3fa0, topDark=0x172f78,
         accent=0xf4f4f4, shirt=0xf7f7f7, hood=0xd5dae4, jacket='varsity', legs='shorts', pants=0x3a3f4a,
         shoeAccent=0x1f5fd0, bag=0xc9802b, letter=0xf6c21b, headphones=True, build=1.),
    dict(id='neso', name='Neso', skin=0xf1bd92, head='hijab', headColor=0xf27aa8, sunglasses=True, top=0xf47fb0, topDark=0xd9608f,
         accent=0xffb3cf, jacket='hoodie', legs='jeans', pants=0x5b80b8, shoeAccent=0xf06ea0, bag=0xe0508a, lashes=True, build=.95),
    dict(id='yousef', name='Yousef', skin=0xf0b98f, hair=0x2b1a10, hairStyle='short', head='capBack', headColor=0xffc21a,
         top=0xffc21a, topDark=0xe0a40c, accent=0xffd64d, jacket='hoodie', legs='cargo', pants=0x2f3540, shoeAccent=0xb8bcc6,
         bag=0x1f3c8a, build=1.22, chubby=True),
    dict(id='laila', name='Laila', skin=0xf1bd92, hair=0x5a3418, hairStyle='long', head='cap', headColor=0x8b4fd8,
         top=0x9b6be8, topDark=0x7d4fcc, accent=0xbfa2f2, shirt=0xffffff, jacket='open', legs='cargo', pants=0x4b3f6b,
         shoeAccent=0x8b4fe0, bag=0x8a4fd8, lashes=True, build=.95),
    dict(id='aser', name='Aser', skin=0xf1bd92, hair=0x3b2314, hairStyle='curly', glasses=True, top=0x3fa945, topDark=0x2f8a36,
         accent=0x62cc66, jacket='hoodie', legs='pants', pants=0x2e3440, shoeAccent=0x3fa945, bag=0x2f7d36, tablet=True, build=.97),
    dict(id='salma', name='Salma', skin=0xf1bd92, head='hijab', headColor=0xf6f6f6, top=0x2f6fd6, topDark=0x2358b0,
         accent=0x6c9ff0, shirt=0xffffff, jacket='open', legs='jeans', pants=0x7aa3d8, shoeAccent=0xc8ccd6, bag=0x1f3c8a,
         books=True, lashes=True, build=.95),
]

MAL = dict(skin=0xf1bd92, hair=0x4a2a17, hairStyle='curly', build=1.)
SKINS = [
    dict(MAL, id='explorer', name='Explorer Malek', hairStyle='curlyUnder', head='safari', headColor=0xd8be84, headAccent=0x6b4423,
         top=0x9c7d45, topDark=0x7a5f30, accent=0xb08f52, shirt=0xe9dcb8, sleeve=0xe9dcb8, shortSleeves=True, jacket='vest',
         legs='shorts', pants=0x8a6d3b, feet='boot', shoes=0x6b4423, shoeAccent=0x4a2e17, bag=0x7a5630),
    dict(MAL, id='pharaoh', name='Pharaoh Malek', hairStyle=None, head='nemes', headColor=0xe8b923, headAccent=0x1f4fb5,
         top=0xf5f0e0, topDark=0xe0d7bd, accent=0xe8b923, shortSleeves=True, jacket='tee', collar=True, legs='kilt', pants=0xf5f0e0,
         feet='sandal', shoes=0xc9992e, shoeAccent=0xe8b923, bag=None),
    dict(MAL, id='football', name='Football Malek', top=0xd92b2b, topDark=0xb01f1f, accent=0xffffff, shortSleeves=True, jacket='jersey',
         legs='shorts', pants=0xffffff, socks=0xd92b2b, feet='cleat', shoes=0x1d1d1d, shoeAccent=0xffffff, bag=None, number='10'),
    dict(MAL, id='space', name='Space Malek', head='helmet', top=0xf2f4f8, topDark=0xd4d8e2, accent=0x2f6fe0, jacket='suit',
         legs='pants', pants=0xeef0f6, feet='boot', shoes=0xc8ccd6, shoeAccent=0x2f6fe0, bag=0xd0d4dc, gloves=0xf2f4f8, patch=0xe03a3a, build=1.05),
    dict(MAL, id='winter', name='Winter Malek', hairStyle='curlyUnder', head='beanie', headColor=0x2e6be0, headAccent=0xffffff, goggles=True,
         top=0x2e6be0, topDark=0x2557b8, accent=0x86b3ff, jacket='puffer', legs='pants', pants=0x283246, feet='boot', shoes=0xf2f2f2,
         shoeAccent=0x2e6be0, bag=0xf2b71b, gloves=0x1f3c8a, build=1.1),
    dict(MAL, id='festivalSkin', name='Festival Malek', top=0x8a3fc0, topDark=0x6d2f9a, accent=0xf2c21b, shirt=0xf2c21b, jacket='festival',
         legs='shorts', pants=0x3a2a55, shoeAccent=0xd92b2b, bag=0xd92b2b, lantern=True),
]
ALL = CHARS + SKINS
def pick(only):
    if only == 'skins': return SKINS
    if not only or only == 'chars': return CHARS
    return [c for c in ALL if c['id'] == only]

def lin(h):
    c = [((h >> s) & 255) / 255 for s in (16, 8, 0)]
    return tuple(x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4 for x in c)

MATS = {}
KINDS = dict(skin=dict(rough=.45, sss=.25), fabric=dict(rough=.78, sheen=.5), hair=dict(rough=.55, sheen=.35, coat=.05),
             plastic=dict(rough=.3, coat=.6), rubber=dict(rough=.6), glossy=dict(rough=.1, coat=1.), glow=dict(rough=.1, emit=3.),
             matte=dict(rough=.7))
def M(kind, hexc, **over):
    key = f'{kind}_{hexc:06x}' + ''.join(f'_{k}{v}' for k, v in over.items())
    if key in MATS: return MATS[key]
    p = {**KINDS[kind], **over}
    m = bpy.data.materials.new(key); m.use_nodes = True
    I = m.node_tree.nodes['Principled BSDF'].inputs
    I['Base Color'].default_value = (*lin(hexc), 1); I['Roughness'].default_value = p.get('rough', .6)
    if p.get('sss'): I['Subsurface Weight'].default_value = p['sss']; I['Subsurface Radius'].default_value = (1., .4, .25); I['Subsurface Scale'].default_value = .02
    if p.get('sheen'): I['Sheen Weight'].default_value = p['sheen']; I['Sheen Roughness'].default_value = .5
    if p.get('coat'): I['Coat Weight'].default_value = p['coat']; I['Coat Roughness'].default_value = .15
    if p.get('emit'): I['Emission Color'].default_value = (*lin(hexc), 1); I['Emission Strength'].default_value = p['emit']
    if p.get('alpha'): I['Alpha'].default_value = p['alpha']
    MATS[key] = m; return m

def darker(h, k):
    return (min(255, int(((h >> 16) & 255) * k)) << 16) | (min(255, int(((h >> 8) & 255) * k)) << 8) | min(255, int((h & 255) * k))

# ---------------- geometry helpers ----------------
PARTS = []
def link(ob, bone):
    SC.collection.objects.link(ob); ob['bone'] = bone; PARTS.append(ob); return ob
def smooth(me):
    for p in me.polygons: p.use_smooth = True
def bake(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    name, bone, mats, mw = ob.name, ob.get('bone'), [s.material for s in ob.material_slots], ob.matrix_world.copy()
    if ob in PARTS: PARTS.remove(ob)
    bpy.data.objects.remove(ob)
    me.materials.clear()
    for m in mats: me.materials.append(m)
    o = bpy.data.objects.new(name, me); o.matrix_world = mw; smooth(me)
    return link(o, bone)
def meta(name, bone, material, elems, res=.007):
    mb = bpy.data.metaballs.new(name); mb.resolution = res; mb.render_resolution = res; mb.threshold = .6
    ob = bpy.data.objects.new(name, mb)
    for e in elems:
        el = mb.elements.new(); el.type = e.get('t', 'BALL'); el.co = e['co']
        s = e.get('s', 2.); el.stiffness = s; el.radius = e['r'] * STIFF.get(s, K)
        if 'size' in e: el.size_x, el.size_y, el.size_z = e['size']
        if 'rot' in e: el.rotation = Euler(e['rot']).to_quaternion()
        if e.get('neg'): el.use_negative = True
    ob.data.materials.append(material); link(ob, bone)
    return bake(ob)
def prim(kind, name, bone, material, loc, scale=(1, 1, 1), rot=(0, 0, 0), **kw):
    if kind == 'torus':
        bpy.ops.mesh.primitive_torus_add(major_radius=kw.get('R', 1), minor_radius=kw.get('r', .2), major_segments=48, minor_segments=12)
        t = bpy.context.active_object; t.name = name; t.location, t.scale, t.rotation_euler = loc, scale, rot
        for c in list(t.users_collection): c.objects.unlink(t)
        t.data.materials.append(material); smooth(t.data); return link(t, bone)
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    if kind == 'sphere': bmesh.ops.create_uvsphere(bm, u_segments=kw.get('u', 32), v_segments=kw.get('v', 16), radius=1)
    elif kind == 'cyl': bmesh.ops.create_cone(bm, cap_ends=True, segments=kw.get('seg', 32), radius1=1, radius2=kw.get('top', 1), depth=1)
    elif kind == 'cube': bmesh.ops.create_cube(bm, size=1)
    bm.to_mesh(me); bm.free(); smooth(me); me.materials.append(material)
    ob = bpy.data.objects.new(name, me); ob.location, ob.scale, ob.rotation_euler = loc, scale, rot
    link(ob, bone)
    if kw.get('bevel'):
        b = ob.modifiers.new('bev', 'BEVEL'); b.width = kw['bevel']; b.segments = 4; b.limit_method = 'NONE'
        ob.modifiers.new('sub', 'SUBSURF').levels = 2
        ob = bake(ob)
    return ob
def tube(name, bone, material, pts, r, radii=None):
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = r; cu.bevel_resolution = 3; cu.resolution_u = 8
    cu.use_fill_caps = True
    sp = cu.splines.new('BEZIER'); sp.bezier_points.add(len(pts) - 1)
    for i, (bp, p) in enumerate(zip(sp.bezier_points, pts)):
        bp.co = p; bp.radius = radii[i] if radii else 1.; bp.handle_left_type = bp.handle_right_type = 'AUTO'
    ob = bpy.data.objects.new(name, cu); cu.materials.append(material); link(ob, bone)
    return bake(ob)
def cap(name, bone, material, loc, radius, angle, axis, scale=(1, 1, 1)):
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=64, radius=radius)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z / radius < math.cos(angle) - 1e-4], context='VERTS')
    q = Vector((0, 0, 1)).rotation_difference(Vector(axis).normalized())
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=q.to_matrix())
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); smooth(me); me.materials.append(material)
    ob = bpy.data.objects.new(name, me); ob.location = loc; ob.scale = scale
    return link(ob, bone)
def boolean(target, cutter):
    m = target.modifiers.new('bool', 'BOOLEAN'); m.object = cutter; m.operation = 'DIFFERENCE'; m.solver = 'EXACT'
    nb = bake(target)
    if cutter in PARTS: PARTS.remove(cutter)
    bpy.data.objects.remove(cutter)
    return nb

# =====================================================================
GB = dict(malek=1., neso=.95, yousef=1.28, laila=.95, aser=.97, salma=.95, explorer=1., pharaoh=1., football=1., space=1.05, winter=1.1, festivalSkin=1.)   # game rig build factor (Eg[...].build)

def build(ch):
    b = ch['build']; bw = min(b, 1.15); gb = GB[ch['id']]
    rng = random.Random(hash(ch['id']) & 0xffff)
    SK = M('skin', ch['skin']); SKD = M('skin', darker(ch['skin'], .88))
    TOP = M('fabric', ch['top']); TOPD = M('fabric', ch['topDark']); ACC = M('fabric', ch['accent'])
    PANTS = M('fabric', ch['pants']); PANTSD = M('fabric', darker(ch['pants'], .78))
    WHITE = M('fabric', 0xf7f7f7); DARK = M('matte', 0x1e1008)
    HAIR = M('hair', ch.get('hair', 0x2b1a10)); BROW = M('matte', darker(ch.get('hair', 0x3a2010), .75))
    hijab = ch.get('head') == 'hijab'

    # ======================= HEAD =======================
    HC = Vector((0, 0, 1.54)); ch_k = 1.12 if ch.get('chubby') else 1.
    head = meta('head', 'head', SK, [
        dict(t='ELLIPSOID', co=HC, r=.31, size=(1, .97, 1.03)),
        dict(t='ELLIPSOID', co=(0, -.05, 1.41), r=.24, size=(1.02 * ch_k, .86, .9)),
        dict(co=(0, -.15, 1.33), r=.085, s=1.5),
        dict(co=(-.135 * ch_k, -.17, 1.445), r=.105 * ch_k, s=1.5), dict(co=(.135 * ch_k, -.17, 1.445), r=.105 * ch_k, s=1.5),
        dict(co=(0, -.29, 1.45), r=.03, s=2.),
        dict(t='ELLIPSOID', co=(-.3, 0, 1.48), r=.065, size=(.6, .8, 1.15), s=1.5),
        dict(t='ELLIPSOID', co=(.3, 0, 1.48), r=.065, size=(.6, .8, 1.15), s=1.5)])
    bvh = BVHTree.FromObject(head, bpy.context.evaluated_depsgraph_get())
    def surf(x, z):
        hit = bvh.ray_cast(Vector((x, -2, z)), Vector((0, 1, 0)))[0]
        return hit.y if hit else -.28
    # closed natural smile
    def smile_pts(off, n=13, w=.072, depth=.026, z0=1.372):
        return [Vector((x, surf(x, z) + off, z)) for x, z in
                ((-w + 2 * w * i / (n - 1), z0 - depth * (1 - ((-w + 2 * w * i / (n - 1)) / w) ** 2)) for i in range(n))]
    MOUTH = M('matte', 0x4a1218)
    head = boolean(head, tube('smileCut', 'head', MOUTH, smile_pts(0), .008, [.7] + [1] * 11 + [.7]))
    tube('smile', 'head', MOUTH, smile_pts(.005), .0055, [.35] + [1] * 11 + [.35])
    for s in (-1, 1):
        x0, z0 = s * .072, 1.372
        tube('smileCorner', 'head', MOUTH, [Vector((x0, surf(x0, z0) + .006, z0)), Vector((x0 + s * .01, surf(x0 + s * .01, z0 + .012) + .006, z0 + .012))], .005, [.8, .2])
        if not hijab: prim('sphere', 'earIn', 'head', SKD, (s * .312, -.025, 1.48), (.018, .03, .045))
    # eyes
    ER = .096; LID_A = Vector((0, math.sin(.62), math.cos(.62))); LID_ANG = math.radians(74)
    for s in (-1, 1):
        c = Vector((s * .112, surf(s * .112, 1.54) + ER - .018, 1.54)); look = Vector((0, -1, .02))
        prim('sphere', 'eye', 'head', M('glossy', 0xffffff), c, (ER,) * 3)
        cap('irisRim', 'head', M('glossy', 0x2e150a), c, ER * 1.004, .72, look)
        cap('iris', 'head', M('glossy', 0x6b3a1a), c, ER * 1.007, .64, look)
        cap('pupil', 'head', M('glossy', 0x0a0604), c, ER * 1.011, .3, look)
        cap('lid', 'head', SK, c, ER * 1.075, LID_ANG, LID_A)
        u = Vector((1, 0, 0)); v = LID_A.cross(u); ring = []
        for k in range(40):
            ph = 2 * P * k / 40
            d = math.cos(LID_ANG) * LID_A + math.sin(LID_ANG) * (math.cos(ph) * u + math.sin(ph) * v)
            if d.y < -.25: ring.append(c + d * ER * 1.09)
        ring.sort(key=lambda p: s * p.x)
        pl = ring[::2] if (len(ring) - 1) % 2 == 0 else ring[::2] + [ring[-1]]
        tube('liner', 'head', DARK, pl, .009, [.6 + .8 * i / max(1, len(pl) - 1) for i in range(len(pl))])
        if ch.get('lashes'):
            o = pl[-1]
            for dx, dz in ((.03, .018), (.024, .036)):
                tube('lash', 'head', DARK, [o, o + Vector((s * dx * .55, -.004, dz * .5)), o + Vector((s * dx, 0, dz))], .0055, [1, .7, .15])
        prim('sphere', 'hl', 'head', M('glow', 0xffffff), c + Vector((s * .02 + .014, -ER * .88, .036)), (.02,) * 3)
        prim('sphere', 'hl2', 'head', M('glow', 0xffffff), c + Vector((-.02, -ER * .95, -.026)), (.009,) * 3)
        tube('brow', 'head', BROW, [(s * x, surf(s * x, z) - .006, z) for x, z in ((.04, 1.716), (.085, 1.728), (.135, 1.722), (.18, 1.7))],
             .018 if ch.get('lashes') else .02, [.9, 1, .85, .45])
    if ch.get('glasses'):
        FR = M('plastic', 0x1d1d1d)
        for s in (-1, 1):
            c = Vector((s * .112, surf(s * .112, 1.54) - .02, 1.54))
            prim('torus', 'lens', 'head', FR, c, (1, 1, 1), (P / 2, 0, 0), R=.088, r=.011)
            tube('temple', 'head', FR, [c + Vector((s * .085, 0, .01)), Vector((s * .27, -.15, 1.56)), Vector((s * .3, .02, 1.5))], .008)
        tube('bridge', 'head', FR, [Vector((-.03, surf(-.03, 1.555) - .022, 1.555)), Vector((0, surf(0, 1.565) - .028, 1.565)), Vector((.03, surf(.03, 1.555) - .022, 1.555))], .009)

    # ======================= HAIR / HEADWEAR =======================
    HO = HC + Vector((0, .02, .04)); crown = Vector((0, .25, 1)).normalized()
    hs = ch.get('hairStyle'); hw = ch.get('head')
    if hs:
        meta('hairCap', 'head', HAIR, [dict(t='ELLIPSOID', co=(0, .03, 1.58), r=.325, size=(1, 1, 1.0)),
             dict(t='ELLIPSOID', co=(0, -.33, 1.43), r=.27, size=(1.2, 1, 1.15), neg=True),
             dict(t='ELLIPSOID', co=(0, -.12, 1.22), r=.26, size=(1.3, 1.2, .7), neg=True)]
             + ([dict(t='ELLIPSOID', co=(s * .29, -.05, 1.52), r=.04, size=(.6, 1, 1.8)) for s in (-1, 1)] if hs == 'short' else []), res=.008)
    if hs in ('curly', 'curlyUnder'):
        n, gold = 190, P * (3 - math.sqrt(5))
        for i in range(n):
            z = 1 - i / (n - 1) * 2; rad = math.sqrt(1 - z * z); th = gold * i
            d = Vector((math.cos(th) * rad, math.sin(th) * rad, z))
            if d.z < (-.4 if d.y > .15 else -.08): continue
            if d.y < -.2 and d.z < .5 and abs(d.x) < .85: continue
            if d.z < .05 and abs(d.x) > .5 and d.y < .2: continue
            if ch.get('glasses') and abs(d.x) > .75 and d.z < .25: continue      # keep temples clear
            if hs == 'curlyUnder' and d.z > .3: continue                       # crown is under the hat
            t = (d - crown); t = t - d * t.dot(d)
            t = t.normalized() if t.length > 1e-3 else Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), 0)).normalized()
            side = d.cross(t); sg = 1 if i % 2 else -1
            L = .07 + rng.random() * .045; R = .05 + rng.random() * .02
            g = Vector((0, 0, -.035)) if d.z < .55 else Vector((0, 0, 0)); root = HO + d * .29
            tube('lock', 'head', HAIR, [root, root + d * .065 + t * L * .5 + g * .4, root + d * .1 + t * L * .8 + side * sg * .04 + g,
                 root + d * .08 + t * L * .45 + side * sg * .085 + g, root + d * .045 + t * L * .3 + side * sg * .06], R, [1, 1, .85, .55, .2])
        for k in range(7 if hs == 'curly' else 0):
            x0 = -.12 + k * .045
            tube('fringe', 'head', HAIR, [Vector(p) for p in ((x0, -.12, 1.84), (x0 - .03, -.26, 1.82), (x0 - .07, -.31, 1.75), (x0 - .1, -.29, 1.69 + rng.random() * .02))],
                 .045 + rng.random() * .01, [1, .9, .6, .2])
    if hs == 'long':
        # wavy locks falling from under the cap down to the shoulder blades, plus face-framing strands
        meta('hairBack', 'head', HAIR, [dict(t='ELLIPSOID', co=(0, .14, 1.42), r=.27, size=(1.05, .8, 1.3)), dict(t='ELLIPSOID', co=(0, .2, 1.2), r=.2, size=(1.2, .7, 1.))], res=.008)
        for k in range(46):
            a = -P * .92 + k / 45 * P * 1.84                   # around the head, open at the face
            dx, dy = math.sin(a), math.cos(a)                  # dy>0 = back
            if dy < -.45: continue
            root = Vector((dx * .32, dy * .31 + .02, 1.66))
            front = dy < 0
            length = .42 if front else .6 + rng.random() * .08
            pts = []
            for j in range(6):
                f = j / 5
                out = -.01 + f * .045
                wave = math.sin(f * 7 + k) * .025
                pts.append(Vector((dx * (.32 + out) + wave * dy, dy * (.31 + out) + .02 - wave * dx, 1.66 - f * length)))
            tube('long', 'head', HAIR, pts, .05 + rng.random() * .012, [1, 1, .95, .85, .65, .25])
        for k in range(5):                                     # side-swept bangs under the brim
            x0 = -.14 + k * .06
            tube('bang', 'head', HAIR, [Vector((x0, -.26, 1.75)), Vector((x0 + .04, -.305, 1.72)), Vector((x0 + .08, -.3, 1.685))], .032, [1, .7, .2])
    if hw in ('cap', 'capBack'):
        CAPM = M('fabric', ch['headColor']); sgn = 1 if hw == 'cap' else -1      # +1: brim at the front (-Y)
        cap('capDome', 'head', CAPM, HC + Vector((0, .03, .08)), .35, math.radians(96), (0, .36, 1), (1, 1, .92))
        bco = (0, -.36, 1.735) if sgn > 0 else (0, .37, 1.56)
        meta('brim', 'head', M('fabric', darker(ch['headColor'], .92)), [dict(t='ELLIPSOID', co=bco, r=.16,
             size=(1, 1.15, .1), rot=(.18 if sgn > 0 else -.35, 0, 0))], res=.005)
        prim('sphere', 'capButton', 'head', CAPM, (0, .14, 1.93), (.03, .03, .018))
        for k in range(6):                                     # panel seams
            a = k / 6 * 2 * P
            tube('seam', 'head', M('fabric', darker(ch['headColor'], .8)),
                 [Vector((0, .14, 1.935)), Vector((math.sin(a) * .25, .1 + math.cos(a) * .25, 1.87 - .08 * max(0, -math.cos(a)))), Vector((math.sin(a) * .35, .03 + math.cos(a) * .35, 1.72 - .2 * max(0, math.cos(a)) + .0))], .004)
        if hw == 'cap': prim('cyl', 'emblem', 'head', M('plastic', 0xffd23f), (0, -.29, 1.83), (.04, .04, .006), (math.radians(50), 0, 0))
        else:   # snapback opening + strap now facing forward
            tube('snap', 'head', M('plastic', 0x222222), [Vector((-.07, -.315, 1.75)), Vector((0, -.325, 1.78)), Vector((.07, -.315, 1.75))], .009)
            meta('snapHair', 'head', HAIR, [dict(t='ELLIPSOID', co=(0, -.3, 1.79), r=.05, size=(1.2, .6, .8))], res=.005)
    if hs == 'curlyUnder':                               # short curls peeking under the brim
        for k in range(6):
            x0 = -.15 + k * .06
            tube('fringeU', 'head', HAIR, [Vector((x0, -.22, 1.73)), Vector((x0 - .02, -.3, 1.71)), Vector((x0 - .04, -.315, 1.67))], .04, [1, .7, .2])
    if hw == 'safari':
        HT = M('fabric', ch['headColor']); BD = M('fabric', ch['headAccent'])
        cap('hatDome', 'head', HT, HC + Vector((0, .02, .1)), .345, math.radians(94), (0, .15, 1), (1, 1, .86))
        meta('hatBrim', 'head', HT, [dict(t='ELLIPSOID', co=(0, .02, 1.72), r=.52, size=(1, 1, .03), rot=(-.1, 0, 0))], res=.007)
        prim('torus', 'hatBand', 'head', BD, (0, .02, 1.76), (1, 1, 1), (-.1, 0, 0), R=.33, r=.03)
    if hw == 'beanie':
        BN = M('fabric', ch['headColor']); RW = M('fabric', ch['headAccent'])
        cap('beanie', 'head', BN, HC + Vector((0, .03, .07)), .355, math.radians(95), (0, .25, 1), (1, 1, 1.04))
        prim('torus', 'beanieRim', 'head', RW, (0, .05, 1.6), (1, 1, 1), (-.25, 0, 0), R=.345, r=.05)
        prim('sphere', 'pom', 'head', RW, (0, .12, 1.98), (.075,) * 3)
        if ch.get('goggles'):
            prim('torus', 'gogStrap', 'head', M('matte', 0x1d2433), (0, .05, 1.7), (1, 1, 1), (-.25, 0, 0), R=.36, r=.017)
            for s in (-1, 1):
                rot = (P / 2 - .4, 0, 0)
                prim('torus', 'gogFrame', 'head', M('plastic', 0x1d2433), (s * .09, -.31, 1.77), (1, 1, 1), rot, R=.065, r=.018)
                prim('cyl', 'gogLens', 'head', M('glossy', 0x7fd0ff), (s * .09, -.31, 1.77), (.064, .064, .012), rot)
    if hw == 'helmet':
        prim('sphere', 'visor', 'head', M('glossy', 0xcfe6ff, alpha=.16), (0, -.01, 1.58), (.5, .5, .52), u=48, v=32)
    if hw == 'nemes':
        G = M('plastic', ch['headColor'], rough=.35); BL = M('plastic', ch['headAccent'], rough=.35)
        ax = Vector((0, .3, 1)).normalized(); C0 = HC + Vector((0, .02, .03)); R0 = .355
        cap('nemes', 'head', G, C0, R0, math.radians(100), ax)
        for h in (.1, .17, .24, .3):
            prim('torus', 'nemesStripe', 'head', BL, C0 + ax * h, (1, 1, 1), (-.29, 0, 0), R=math.sqrt(R0 ** 2 - h ** 2) + .004, r=.012)
        prim('torus', 'nemesBand', 'head', G, C0 + ax * -.03, (1, 1, 1), (-.29, 0, 0), R=R0 + .006, r=.022)
        for s in (-1, 1):
            meta('lappet', 'head', G, [dict(t='ELLIPSOID', co=(s * .29, -.07, 1.3), r=.11, size=(.55, 1, 2.6))], res=.007)
            for z in (1.18, 1.28, 1.38):
                tube('lappetStripe', 'head', BL, [Vector((s * .25, -.15, z)), Vector((s * .3, -.165, z)), Vector((s * .35, -.13, z))], .011)
        meta('nemesTail', 'head', G, [dict(t='ELLIPSOID', co=(0, .27, 1.35), r=.12, size=(1, .6, 1.9))], res=.007)
        tube('uraeus', 'head', G, [Vector((0, -.33, 1.69)), Vector((0, -.37, 1.75)), Vector((0, -.375, 1.81))], .014, [1, 1, .7])
        prim('sphere', 'uraeusHead', 'head', G, (0, -.38, 1.82), (.022, .016, .024))
    if hijab:
        HJ = M('fabric', ch['headColor'])
        meta('hijab', 'head', HJ, [
            dict(t='ELLIPSOID', co=(0, .01, 1.56), r=.35, size=(1, 1, 1.03)),
            dict(t='ELLIPSOID', co=(0, -.05, 1.3), r=.24, size=(1.15, 1, .75)),          # under the chin
            dict(t='ELLIPSOID', co=(0, .02, 1.22), r=.18, size=(1.1, 1, 1.)),           # neck
            dict(t='ELLIPSOID', co=(0, -.37, 1.49), r=.2, size=(1., 1, 1.32), neg=True)])   # face opening
        meta('hijabDrape', 'torso', HJ, [
            dict(t='ELLIPSOID', co=(0, 0, 1.13), r=.24, size=(1.08, .8, .36)),
            dict(t='ELLIPSOID', co=(0, -.12, 1.05), r=.12, size=(1.3, .5, .9)),
            dict(t='ELLIPSOID', co=(0, .12, 1.03), r=.15, size=(1.15, .5, 1.))])
        if ch.get('sunglasses'):
            FR = M('plastic', 0xff5f9e); LENS = M('glossy', 0x3a1530)
            for s in (-1, 1):
                rot = (math.radians(28), 0, 0)
                prim('torus', 'shadesFrame', 'head', FR, (s * .085, -.2, 1.86), (1, 1, 1), rot, R=.058, r=.011)
                prim('cyl', 'shadesLens', 'head', LENS, (s * .085, -.2, 1.86), (.056, .056, .006), rot)
            tube('shadesBridge', 'head', FR, [Vector((-.03, -.21, 1.865)), Vector((0, -.215, 1.875)), Vector((.03, -.21, 1.865))], .008)

    # ======================= TORSO =======================
    J = ch['jacket']; tb = [dict(t='ELLIPSOID', co=(0, 0, .95), r=.22, size=(b, .74 * bw, 1.12)),
                           dict(t='ELLIPSOID', co=(0, -.005, .8), r=.205, size=(b * (1.04 if ch.get('chubby') else 1), .78 * bw * (1.08 if ch.get('chubby') else 1), .7)),
                           dict(co=(-.2 * b, 0, 1.1), r=.1), dict(co=(.2 * b, 0, 1.1), r=.1)]
    jacket = meta('jacket', 'torso', TOP, tb)
    fy = -.165 * bw * (1.08 if ch.get('chubby') else 1)          # front surface at belly height
    if J in ('varsity', 'open', 'vest', 'festival'):
        jacket = boolean(jacket, prim('cube', 'slot', 'torso', TOP, (0, -.2 * bw, .93), (.2 if J == 'vest' else .13, .2, .5)))
        meta('tee', 'torso', M('fabric', ch.get('shirt', 0xf7f7f7)), [dict(t='ELLIPSOID', co=(0, .005, .94), r=.205, size=(b, .74 * bw, 1.12)),
                                                                     dict(t='ELLIPSOID', co=(0, 0, .8), r=.19, size=(b, .78 * bw, .7))])
        for s in (-1, 1):
            lx = .1 if J == 'vest' else .066
            tube('lapel', 'torso', ACC if J == 'festival' else TOPD, [(s * lx, fy - .003, .72), (s * lx, fy - .013, .9), (s * (lx + .004), fy + .005, 1.08), (s * .06, -.12, 1.15)], .012)
    prim('torus', 'hem', 'torso', ACC if J in ('varsity', 'festival', 'puffer') else TOPD, (0, 0, .72), (b, .76 * bw, 1), R=.205, r=.028)
    if J == 'vest':
        for s in (-1, 1):
            prim('cube', 'vestPocket', 'torso', TOPD, (s * .14, fy + .008, .97), (.075, .02, .08), (0, 0, s * math.radians(-18)), bevel=.01)
            prim('cube', 'vestFlap', 'torso', TOPD, (s * .14, fy - .002, 1.015), (.08, .02, .025), (0, 0, s * math.radians(-18)), bevel=.006)
            tube('shirtCollar', 'torso', M('fabric', ch['shirt']), [(s * .02, -.15, 1.13), (s * .07, -.17, 1.11), (s * .09, -.15, 1.13)], .012)
    if J == 'festival':
        for z in (.85, .93, 1.01): prim('sphere', 'button', 'torso', M('plastic', ch['accent']), (0, fy - .02, z), (.014,) * 3)
    if ch.get('collar'):            # pharaoh broad collar (usekh)
        for k, col in enumerate((ch['headAccent'], ch['accent'], ch['headAccent'], ch['accent'])):
            prim('torus', 'usekh', 'torso', M('plastic', col, rough=.35), (0, 0, 1.16 - k * .012), (1.12, .92, .4), R=.115 + k * .035, r=.022)
    if J == 'varsity':
        prim('torus', 'hemStripe', 'torso', TOP, (0, 0, .755), (b, .76 * bw, 1), R=.214, r=.009)
        meta('hood', 'torso', M('fabric', ch['hood']), [dict(t='ELLIPSOID', co=(0, .02, 1.16), r=.13, size=(1.2, 1, .5)),
                                                        dict(t='ELLIPSOID', co=(0, .14, 1.14), r=.12, size=(1.2, .7, .8))])
        cu = bpy.data.curves.new('M', 'FONT'); cu.body = 'M'; cu.size = .085; cu.extrude = .006; cu.bevel_depth = .002; cu.align_x = 'CENTER'
        t = bpy.data.objects.new('letter', cu); t.location = (.115, -.172, .99); t.rotation_euler = (P / 2, 0, math.radians(18))
        cu.materials.append(M('plastic', ch['letter'])); link(t, 'torso'); bake(t)
        prim('cube', 'patch', 'torso', TOPD, (.112, -.165, 1.02), (.075, .01, .075), (0, 0, math.radians(18)), bevel=.008)
    elif J == 'hoodie':
        if not hijab:
            meta('hood', 'torso', TOPD, [dict(t='ELLIPSOID', co=(0, .03, 1.16), r=.14, size=(1.25 * b, 1, .5)),
                                        dict(t='ELLIPSOID', co=(0, .15, 1.13), r=.13, size=(1.25 * b, .75, .85))])
        prim('cube', 'pocket', 'torso', TOPD, (0, fy + .004, .79), (.28 * b, .016, .13), (math.radians(-8), 0, 0), bevel=.007)
        for s in (-1, 1):
            tube('string', 'torso', WHITE, [(s * .045, -.13 * bw, 1.13), (s * .048, fy - .02, 1.02), (s * .052, fy - .03, .93)], .0065)
            prim('cyl', 'aglet', 'torso', M('plastic', 0xe6e6e6), (s * .052, fy - .03, .91), (.009, .009, .03))
    elif J == 'jersey':
        tube('vneck', 'torso', ACC, [(-.075, -.11, 1.16), (-.03, -.16, 1.1), (0, fy - .012, 1.04), (.03, -.16, 1.1), (.075, -.11, 1.16)], .012)
        for s in (-1, 1): tube('sideTrim', 'torso', ACC, [(s * .215 * b, -.03, .74), (s * .225 * b, -.02, .95), (s * .2 * b, 0, 1.1)], .01)
        cu = bpy.data.curves.new('num', 'FONT'); cu.body = ch.get('number', '10'); cu.size = .17; cu.extrude = .005; cu.align_x = 'CENTER'
        t = bpy.data.objects.new('number', cu); t.location = (0, .172 * bw, .9); t.rotation_euler = (P / 2, 0, P)
        cu.materials.append(M('plastic', ch['accent'])); link(t, 'torso'); bake(t)
        prim('cube', 'badge', 'torso', M('plastic', 0xf2c21b), (.11, fy - .002, 1.02), (.05, .01, .06), (0, 0, math.radians(18)), bevel=.012)
    elif J in ('suit', 'puffer'):
        tube('zipper', 'torso', TOPD, [(0, fy - .008, .73), (0, fy - .016, .9), (0, -.15, 1.1)], .008)
        if J == 'suit':
            prim('cube', 'panel', 'torso', M('plastic', 0xa9b0bf), (-.07, fy - .012, .9), (.11, .02, .1), bevel=.01)
            for k, col in enumerate((0xe03a3a, 0x3ad06a, 0x2f6fe0)):
                prim('sphere', 'btn', 'torso', M('glow', col, emit=1.), (-.1 + k * .03, fy - .025, .9), (.012,) * 3)
            prim('cyl', 'patch', 'torso', M('plastic', ch['patch']), (.11, fy - .005, 1.02), (.04, .04, .008), (P / 2 - .25, 0, math.radians(18)))
            for s in (-1, 1): tube('suitStripe', 'torso', ACC, [(s * .22 * b, -.03, .74), (s * .23 * b, -.02, .95), (s * .2 * b, 0, 1.1)], .013)
        else:
            for z, k in ((.82, 1.), (.94, 1.02), (1.06, .9)):
                prim('torus', 'quilt', 'torso', TOPD, (0, 0, z), (b * k, .78 * bw * k, 1), R=.218, r=.016)
            meta('furHood', 'torso', M('fabric', 0xf4f4f4), [dict(t='ELLIPSOID', co=(0, .03, 1.16), r=.15, size=(1.25, 1, .55))])
        meta('collar', 'torso', TOPD if J == 'puffer' else ACC, [dict(t='ELLIPSOID', co=(0, .01, 1.15), r=.12, size=(1.25, 1, .45))])
    else:
        if not hijab and not ch.get('collar'):
            meta('collar', 'torso', TOPD, [dict(t='ELLIPSOID', co=(0, .02, 1.16), r=.12, size=(1.25, 1, .45))])
    if not hijab: prim('cyl', 'neck', 'torso', SK, (0, 0, 1.2), (.06, .06, .14))
    if ch.get('head') == 'helmet':
        prim('torus', 'helmetRing', 'torso', M('plastic', 0xe8ebf2), (0, 0, 1.13), (1.1, 1, 1), R=.2, r=.045)
        prim('torus', 'helmetRing2', 'torso', M('plastic', ch['accent']), (0, 0, 1.165), (1.1, 1, 1), R=.19, r=.015)
    if ch.get('headphones'):
        PH = M('plastic', 0xf4f4f4); PHD = M('matte', 0x2a2a2e)
        prim('torus', 'phonesBand', 'torso', PH, (0, -.03, 1.2), (1.15, 1, 1), (math.radians(-20), 0, 0), R=.13, r=.02)
        for s in (-1, 1):
            prim('cyl', 'cup', 'torso', PH, (s * .15, -.12, 1.17), (.055, .055, .04), (math.radians(70), 0, s * math.radians(35)))
            prim('cyl', 'cupPad', 'torso', PHD, (s * .14, -.105, 1.18), (.045, .045, .042), (math.radians(70), 0, s * math.radians(35)))
    BAG = M('fabric', ch['bag'] or 0); BAGD = M('fabric', darker(ch['bag'] or 0, .75)); by = .17 * bw + .07
    if ch['bag'] is None: by = None
    if by is not None and ch.get('head') == 'helmet':
        for k in range(3): prim('sphere', 'packLight', 'torso', M('glow', 0x5ab0ff, emit=2.), (-.06 + k * .06, by + .085, 1.05), (.014,) * 3)
    if by is not None: prim('cube', 'bag', 'torso', BAG, (0, by, .95), (.3, .15, .34), bevel=.065)
    if by is not None: prim('cube', 'bagPocket', 'torso', BAGD, (0, by + .085, .86), (.22, .05, .15), bevel=.02)
    if by is not None: tube('zip', 'torso', M('matte', 0x2a2a2e), [(-.09, by + .112, .935), (0, by + .116, .938), (.09, by + .112, .935)], .004)
    for s in ((-1, 1) if by is not None else ()):
        tube('strap', 'torso', BAGD, [(s * .13 * b, by - .07, 1.08), (s * .15 * b, .06, 1.17 if not hijab else 1.2), (s * .155 * b, -.09 * bw, 1.13),
                                       (s * .155 * b, fy - .002, 1.0), (s * .14 * b, fy + .002, .8)], .017)

    # ======================= PELVIS =======================
    if ch['legs'] == 'kilt':
        meta('kilt', 'body', PANTS, [dict(t='ELLIPSOID', co=(0, 0, .64), r=.215, size=(b, .8 * bw, .72)), dict(t='ELLIPSOID', co=(0, 0, .5), r=.2, size=(1.1, .85, .45))])
        prim('cube', 'apron', 'body', M('plastic', ch['accent'], rough=.35), (0, -.185, .55), (.1, .02, .2), bevel=.01)
        for z in (.5, .58): tube('apronStripe', 'body', M('plastic', ch['headAccent'], rough=.35), [(-.05, -.198, z), (0, -.2, z), (.05, -.198, z)], .007)
        prim('torus', 'belt', 'body', M('plastic', ch['accent'], rough=.35), (0, 0, .72), (b, .78 * bw, 1), R=.205, r=.025)
    else:
        meta('hips', 'body', PANTS, [dict(t='ELLIPSOID', co=(0, 0, .67), r=.2, size=(b, .76 * bw, .55))])

    # ======================= ARMS =======================
    for s, side in ((-1, 'L'), (1, 'R')):
        x, xf = s * .27 * gb, s * (.27 * gb + .02)
        SLV = M('fabric', ch.get('sleeve', ch['top'])); puff = 1.15 if J == 'puffer' else 1.
        if ch.get('shortSleeves'):
            meta('sleeve' + side, 'arm' + side, SLV, [dict(co=(x, 0, 1.115), r=.09), dict(t='CAPSULE', co=(x, 0, 1.06), r=.075, size=(.04, 1, 1), rot=(0, P / 2, 0))])
            prim('torus', 'sleeveHem' + side, 'arm' + side, ACC if J == 'jersey' else M('fabric', darker(ch.get('sleeve', ch['top']), .9)), (x, 0, 1.02), (1, 1, 1), R=.073, r=.014)
            meta('upperArm' + side, 'arm' + side, SK, [dict(t='CAPSULE', co=(x, 0, .95), r=.055, size=(.08, 1, 1), rot=(0, P / 2, 0))])
            meta('forearm' + side, 'fore' + side, SK, [dict(t='CAPSULE', co=(xf, 0, .76), r=.05, size=(.09, 1, 1), rot=(0, P / 2, 0))])
        else:
            meta('sleeve' + side, 'arm' + side, SLV, [dict(co=(x, 0, 1.115), r=.088 * puff), dict(t='CAPSULE', co=(x, 0, 1.0), r=.07 * puff, size=(.1, 1, 1), rot=(0, P / 2, 0))])
            meta('forearm' + side, 'fore' + side, SLV, [dict(t='CAPSULE', co=(xf, 0, .77), r=.063 * puff, size=(.08, 1, 1), rot=(0, P / 2, 0))])
            if J == 'puffer':
                prim('torus', 'armQuilt' + side, 'arm' + side, TOPD, (x, 0, 1.02), (1, 1, 1), R=.08, r=.012)
                prim('torus', 'foreQuilt' + side, 'fore' + side, TOPD, (xf, 0, .8), (1, 1, 1), R=.074, r=.012)
        for z in (() if ch.get('shortSleeves') else (.665, .69) if J == 'varsity' else (.675,)):
            prim('torus', 'cuff' + side, 'fore' + side, ACC if J in ('varsity', 'suit', 'festival') else TOPD, (xf, 0, z), (1, 1, 1), R=.062 * puff, r=.016 if J == 'varsity' else .022)
        h = [dict(t='ELLIPSOID', co=(xf, -.005, .6), r=.055, size=(.75, .6, 1)),
             dict(t='CAPSULE', co=(xf - s * .045, -.03, .61), r=.02, size=(.025, 1, 1), rot=(0, math.radians(60), s * .6))]
        for fx in (-.03, -.01, .01, .03):
            h.append(dict(t='CAPSULE', co=(xf + fx, -.012, .54 + abs(fx) * .4), r=.018, size=(.022, 1, 1), rot=(0, P / 2 + .25, 0)))
        meta('hand' + side, 'fore' + side, M('fabric', ch['gloves']) if ch.get('gloves') else SK, h, res=.005)
        if s > 0 and ch.get('lantern'):          # Ramadan fanoos hanging from the hand
            GL = M('plastic', 0xd9a520, rough=.3)
            prim('torus', 'lanternRing', 'fore' + side, GL, (xf, -.02, .525), (1, 1, 1), (P / 2, 0, 0), R=.018, r=.004)
            prim('cyl', 'lanternTop', 'fore' + side, GL, (xf, -.02, .49), (.045, .045, .04), top=.25)
            prim('cube', 'lanternGlass', 'fore' + side, M('glow', 0xffb347, emit=2.5), (xf, -.02, .42), (.07, .07, .1))
            for dx, dy in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
                prim('cube', 'lanternBar', 'fore' + side, GL, (xf + dx * .037, -.02 + dy * .037, .42), (.01, .01, .11))
            prim('cyl', 'lanternBase', 'fore' + side, GL, (xf, -.02, .36), (.042, .042, .02))
        if s > 0 and ch.get('tablet'):
            prim('cube', 'tablet', 'fore' + side, M('plastic', 0x30343e), (xf + .04, -.02, .58), (.018, .17, .24), bevel=.008)
            prim('cube', 'screen', 'fore' + side, M('glow', 0x8fe3ff, emit=1.5), (xf + .05, -.02, .58), (.002, .15, .21))
        if s < 0 and ch.get('books'):
            for k, (col, w) in enumerate(((0x2f8f45, .045), (0x3a5fc0, .04))):
                xb = xf - .045 - k * .043
                prim('cube', 'book', 'fore' + side, M('fabric', col), (xb, -.02, .58), (w, .19, .26), bevel=.006)
                prim('cube', 'pages', 'fore' + side, M('matte', 0xf6f1e4), (xb, -.03, .58), (w * .8, .18, .245))

    # ======================= LEGS =======================
    for s, side in ((-1, 'L'), (1, 'R')):
        x = s * .11 * gb; lg = ch['legs']
        if lg == 'kilt':
            meta('thigh' + side, 'leg' + side, SK, [dict(t='CAPSULE', co=(x, 0, .48), r=.065, size=(.09, 1, 1), rot=(0, P / 2, 0))])
            meta('shin' + side, 'shin' + side, SK, [dict(t='CAPSULE', co=(x, 0, .25), r=.055, size=(.1, 1, 1), rot=(0, P / 2, 0))])
        else:
            meta('thigh' + side, 'leg' + side, PANTS, [dict(t='CAPSULE', co=(x, 0, .5), r=(.092 if lg == 'shorts' else .088) * (1.1 if J == 'puffer' else 1), size=(.09, 1, 1), rot=(0, P / 2, 0))])
        if lg == 'kilt': pass
        elif lg == 'shorts' and ch.get('socks'):
            prim('torus', 'hem' + side, 'leg' + side, PANTSD, (x, 0, .385), (1, 1, 1), R=.092, r=.014)
            meta('shin' + side, 'shin' + side, M('fabric', ch['socks']), [dict(t='CAPSULE', co=(x, 0, .25), r=.062, size=(.1, 1, 1), rot=(0, P / 2, 0))])
            prim('torus', 'sockTop' + side, 'shin' + side, ACC, (x, 0, .335), (1, 1, 1), R=.062, r=.012)
        elif lg == 'shorts':
            prim('torus', 'hem' + side, 'leg' + side, PANTSD, (x, 0, .385), (1, 1, 1), R=.092, r=.014)
            meta('shin' + side, 'shin' + side, SK, [dict(t='CAPSULE', co=(x, 0, .27), r=.055, size=(.08, 1, 1), rot=(0, P / 2, 0))])
            prim('cyl', 'sock' + side, 'shin' + side, WHITE, (x, 0, .135), (.06, .06, .1))
            prim('torus', 'sockRib' + side, 'shin' + side, WHITE, (x, 0, .185), (1, 1, 1), R=.06, r=.012)
        else:
            meta('shin' + side, 'shin' + side, PANTS, [dict(t='CAPSULE', co=(x, 0, .25), r=.074, size=(.1, 1, 1), rot=(0, P / 2, 0))])
            if lg == 'jeans': prim('torus', 'cuff' + side, 'shin' + side, M('fabric', darker(ch['pants'], 1.25)), (x, 0, .16), (1, 1, 1), R=.074, r=.024)
            else: prim('torus', 'cuff' + side, 'shin' + side, PANTSD, (x, 0, .16), (1, 1, 1), R=.072, r=.014)
            if lg == 'cargo':
                prim('cube', 'cargo' + side, 'leg' + side, PANTSD, (x + s * .085, 0, .5), (.03, .1, .1), bevel=.01)
                prim('cube', 'cargoFlap' + side, 'leg' + side, PANTSD, (x + s * .09, 0, .555), (.025, .105, .025), bevel=.006)
        ft = ch.get('feet', 'sneaker'); SH = M('plastic', ch.get('shoes', 0xffffff), rough=.35, coat=.4); SA = M('plastic', ch['shoeAccent'])
        if ft == 'sandal':
            meta('foot' + side, 'shin' + side, SK, [dict(t='ELLIPSOID', co=(x, -.03, .05), r=.06, size=(1, 2, .7)), dict(t='CAPSULE', co=(x, 0, .12), r=.05, size=(.05, 1, 1), rot=(0, P / 2, 0))], res=.005)
            meta('sandalSole' + side, 'shin' + side, SH, [dict(t='ELLIPSOID', co=(x, -.03, .012), r=.075, size=(1, 1.9, .2))], res=.005)
            prim('torus', 'toeStrap' + side, 'shin' + side, SA, (x, -.09, .045), (1, .9, .8), (0, P / 2, 0), R=.05, r=.01)
            prim('torus', 'ankleStrap' + side, 'shin' + side, SA, (x, 0, .12), (1, 1, 1), R=.056, r=.01)
            continue
        if ft == 'boot':
            prim('cyl', 'bootShaft' + side, 'shin' + side, SH, (x, .01, .15), (.068, .068, .12))
            prim('torus', 'bootRim' + side, 'shin' + side, M('fabric', 0xf4f4f4) if J == 'puffer' else SA, (x, .01, .21), (1, 1, 1), R=.068, r=.022 if J == 'puffer' else .012)
        meta('shoe' + side, 'shin' + side, SH, [dict(t='ELLIPSOID', co=(x, -.02, .075), r=.08, size=(.95, 1.8, .8)),
             dict(t='ELLIPSOID', co=(x, .07, .1), r=.07), dict(t='ELLIPSOID', co=(x, -.12, .06), r=.065, size=(1.1, 1.1, .75))], res=.005)
        meta('sole' + side, 'shin' + side, M('rubber', 0x2a2a2a if ft == 'cleat' else 0x3a2a1c if ch.get('shoes') == 0x6b4423 else 0xf2f2f2), [dict(t='ELLIPSOID', co=(x, -.025, .03), r=.09, size=(.95, 1.85, .32))], res=.005)
        for o in (1, -1):
            tube('stripe' + side, 'shin' + side, SA, [(x + o * s * .078, .08, .07), (x + o * s * .083, 0, .085), (x + o * s * .078, -.09, .06)], .012)
        prim('cube', 'heelTab' + side, 'shin' + side, SA, (x, .135, .12), (.05, .025, .07), bevel=.01)
        if ft == 'cleat':
            for yy in (-.12, -.04, .04, .1): prim('cyl', 'stud' + side, 'shin' + side, M('plastic', 0xdddddd), (x, yy, .002), (.014, .014, .02))
        for k in range(3):
            prim('cube', 'lace' + side, 'shin' + side, WHITE, (x, -.06 + k * .035, .135 - k * .01), (.07, .012, .012), (math.radians(-20), 0, 0), bevel=.004)

# =====================================================================
from mathutils import Matrix
BUDGET = dict(head=8000, torso=4000, body=400)       # faces per bone after decimation (default 1300)
def joints(gb):
    J = dict(body=(0, 0, .66), torso=(0, 0, .72), head=(0, 0, 1.22))
    for s, side in ((-1, 'L'), (1, 'R')):
        J['arm' + side] = (s * .27 * gb, 0, 1.12); J['fore' + side] = (s * (.27 * gb + .02), 0, .87)
        J['leg' + side] = (s * .11 * gb, 0, .62); J['shin' + side] = (s * .11 * gb, 0, .34)
    return J
def export_char(ch, parts):
    J = joints(GB[ch['id']]); by = {}
    for ob in parts: by.setdefault(ob['bone'], []).append(ob)
    merged = []
    for bone, obs in by.items():
        total = sum(len(o.data.polygons) for o in obs); ratio = min(1., BUDGET.get(bone, 1300) / total)
        baked = []
        for o in obs:
            if ratio < 1 and len(o.data.polygons) >= 20:
                o.modifiers.new('dec', 'DECIMATE').ratio = ratio
                o = bake(o)
            baked.append(o)
        with bpy.context.temp_override(active_object=baked[0], selected_editable_objects=baked, object=baked[0]):
            bpy.ops.object.join()
        m = baked[0]; m.data.transform(m.matrix_world); m.matrix_world = Matrix()
        m.data.transform(Matrix.Translation(-Vector(J[bone])))            # bone-local
        m.name = m.data.name = bone; merged.append(m)
        print('BONE', ch['id'], bone, total, '->', len(m.data.polygons))
    for o in bpy.data.objects: o.select_set(o in merged)
    path = os.path.join(OUT, ch['id'] + '.glb')
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_yup=True, export_apply=True,
                              export_texcoords=False, export_normals=True, export_tangents=False, export_materials='EXPORT',
                              export_cameras=False, export_lights=False, export_animations=False,
                              export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=7,
                              export_draco_position_quantization=14, export_draco_normal_quantization=10)
    print('EXPORTED', path, os.path.getsize(path))
    for o in list(bpy.data.objects): bpy.data.objects.remove(o)
    PARTS.clear()

if MODE == 'export':
    for ch in pick(ONLY):
        build(ch); export_char(ch, list(PARTS))
    sys.exit(0)

sel = pick(ONLY)
for i, ch in enumerate(sel):
    start = len(PARTS)
    build(ch)
    root = bpy.data.objects.new('char_' + ch['id'], None); SC.collection.objects.link(root)
    col = bpy.data.collections.new(ch['id']); SC.collection.children.link(col)
    for ob in PARTS[start:]:
        ob['char'] = ch['id']; ob.parent = root
        for c in list(ob.users_collection): c.objects.unlink(ob)
        col.objects.link(ob)
    root.location.x = (i - (len(sel) - 1) / 2) * 1.05
    print('BUILT', ch['id'], len(PARTS) - start, 'parts', sum(len(o.data.polygons) for o in PARTS[start:] if o.type == 'MESH'), 'faces')

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, ('skins' if ONLY == 'skins' else 'characters') + '.blend'))

if MODE in ('render', 'quick'):
    r = SC.render; r.engine = 'CYCLES'; SC.cycles.device = 'CPU'; SC.cycles.samples = 40 if MODE == 'render' else 24
    SC.cycles.use_denoising = True; r.film_transparent = False
    SC.view_settings.view_transform = 'AgX'; SC.view_settings.look = 'AgX - Punchy'
    w = bpy.data.worlds.new('w'); SC.world = w; w.use_nodes = True
    bg = w.node_tree.nodes['Background']; bg.inputs['Color'].default_value = (*lin(0x1d3c9e), 1); bg.inputs['Strength'].default_value = .6
    bpy.ops.mesh.primitive_circle_add(vertices=64, radius=8, fill_type='NGON'); bpy.context.active_object.data.materials.append(M('matte', 0x2a4fc0))
    def area(name, loc, power, size, color, target=(0, 0, .9)):
        L = bpy.data.lights.new(name, 'AREA'); L.energy = power; L.size = size; L.color = lin(color)
        o = bpy.data.objects.new(name, L); o.location = loc; SC.collection.objects.link(o)
        o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    area('key', (2.5, -4, 3.5), 900, 4, 0xfff0dc); area('fill', (-4, -3, 1.8), 260, 5, 0xcfe0ff)
    area('rim', (-2, 4, 3), 1000, 4, 0xa8d4ff); area('rim2', (3, 3.5, 2.2), 450, 3, 0xffd6a8)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); SC.collection.objects.link(cam); SC.camera = cam
    def shoot(name, loc, target, lens, res):
        cam.location = loc; cam.data.lens = lens; r.resolution_x, r.resolution_y = res
        cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        r.filepath = os.path.join(OUT, name + '.png'); bpy.ops.render.render(write_still=True); print('RENDERED', name)
    if len(sel) > 1: shoot('lineup', (0, -9.5, 1.5), (0, 0, .95), 50, (2400, 1050))
    for i, ch in enumerate(sel):
        x = (i - (len(sel) - 1) / 2) * 1.05
        for c2 in sel: bpy.data.collections[c2['id']].hide_render = c2 is not ch     # portrait: this character only
        shoot(ch['id'] + '-front', (x + 1.1, -3.6, 1.35), (x, 0, .95), 70, (800, 1000))
        if MODE == 'render': shoot(ch['id'] + '-face', (x + .45, -1.8, 1.55), (x, 0, 1.52), 85, (800, 800))
