# Run with Malek - polished trackside props for every world, one GLB.
# Usage: blender -b --factory-startup -P world_props.py -- <out_dir> [render]
#
# Each prop is an empty named after the game prop (building3a, palm, lamp, ...). Its children are
# one mesh per ROLE, named <prop>_<role>, so the game draws each prop in 1-3 draw calls:
#   wall / glass / pole / awning : tinted in the game with the world's own palette colour
#                                  (vertex colours hold only light/dark shading)
#   glow                         : emissive, tinted with the light colour
#   fixed                        : baked vertex colours, not tinted
# Axes match the game props: Blender Z-up; building fronts face +X; props stand on z = 0.
import bpy, bmesh, math, random, sys, os
from mathutils import Vector, Matrix, Euler

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else os.getcwd())
DO_RENDER = len(argv) > 1 and argv[1] == 'render'
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
SC = bpy.context.scene
random.seed(7)

def lin1(c): return c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4
def lin(h, k=1.):
    return tuple(lin1(((h >> s) & 255) / 255) * k for s in (16, 8, 0))

# ---------------- materials: white base x vertex colour (tint happens in the game) ----------------
def role_mat(role, rough, metal=0., emit=0.):
    m = bpy.data.materials.new('rwm_' + role); m.use_nodes = True; m.use_backface_culling = False
    nt = m.node_tree; b = nt.nodes['Principled BSDF']
    b.inputs['Roughness'].default_value = rough; b.inputs['Metallic'].default_value = metal
    vc = nt.nodes.new('ShaderNodeVertexColor'); vc.layer_name = 'Col'
    nt.links.new(vc.outputs['Color'], b.inputs['Base Color'])
    if emit:
        nt.links.new(vc.outputs['Color'], b.inputs['Emission Color']); b.inputs['Emission Strength'].default_value = emit
    return m
MATS = dict(wall=role_mat('wall', .85), glass=role_mat('glass', .3, .1), fixed=role_mat('fixed', .7),
            pole=role_mat('pole', .45, .35), awning=role_mat('awning', .8), glow=role_mat('glow', .4, emit=1.))
TINTED = {'wall', 'glass', 'pole', 'awning', 'glow'}

# ---------------- mesh builders (each returns a bmesh-backed object, colour applied later) ----------------
PARTS = {}            # role -> [(obj, rgb)]
def _obj(bm, name='p'):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); SC.collection.objects.link(o); return o

def put(role, o, color=0xffffff, shade=1.):
    # tinted roles only carry shading; fixed parts carry their real colour
    rgb = (lin1(shade),) * 3 if role in TINTED else lin(color, shade)
    PARTS.setdefault(role, []).append((o, rgb)); return o

def box(role, c, size, color=0xffffff, shade=1., rot=(0, 0, 0), bevel=0.):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    if bevel: bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=1, affect='EDGES')
    bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=Euler(rot).to_matrix(), verts=bm.verts)
    bmesh.ops.translate(bm, vec=Vector(c), verts=bm.verts)
    return put(role, _obj(bm), color, shade)

def cyl(role, c, r1, h, color=0xffffff, shade=1., r2=None, seg=12, rot=(0, 0, 0), caps=True):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=caps, segments=seg, radius1=r1, radius2=r1 if r2 is None else r2, depth=h)
    bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=Euler(rot).to_matrix(), verts=bm.verts)
    bmesh.ops.translate(bm, vec=Vector(c), verts=bm.verts)
    return put(role, _obj(bm), color, shade)

def sphere(role, c, s, color=0xffffff, shade=1., seg=10, rings=6, jitter=0.):
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.)
    for v in bm.verts:
        k = 1 + (random.uniform(-jitter, jitter) if jitter else 0)
        v.co = Vector((v.co.x * s[0] * k, v.co.y * s[1] * k, v.co.z * s[2] * k))
    bmesh.ops.translate(bm, vec=Vector(c), verts=bm.verts)
    return put(role, _obj(bm), color, shade)

def ico(role, c, r, color, shade=1., jitter=.18, sub=2, squash=1.):
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=r)
    for v in bm.verts:
        v.co *= 1 + random.uniform(-jitter, jitter); v.co.z *= squash
    bmesh.ops.translate(bm, vec=Vector(c), verts=bm.verts)
    return put(role, _obj(bm), color, shade)

def strip(role, pts, widths, color, shade=1., up=Vector((0, 0, 1))):
    """Flat ribbon through pts (leaves, fronds, awnings)."""
    bm = bmesh.new(); rows = []
    for i, (p, w) in enumerate(zip(pts, widths)):
        d = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        side = d.cross(up).normalized() * w / 2
        rows.append((bm.verts.new(p - side), bm.verts.new(p + side)))
    for a, b in zip(rows, rows[1:]): bm.faces.new((a[0], a[1], b[1], b[0]))
    return put(role, _obj(bm), color, shade)

def tube(role, pts, r, color=0xffffff, shade=1., seg=6):
    bm = bmesh.new(); rings = []
    for i, p in enumerate(pts):
        d = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        a = d.orthogonal().normalized(); b = d.cross(a)
        rr = r[i] if isinstance(r, (list, tuple)) else r
        rings.append([bm.verts.new(p + (a * math.cos(t) + b * math.sin(t)) * rr)
                      for t in (2 * math.pi * k / seg for k in range(seg))])
    for A, B in zip(rings, rings[1:]):
        for k in range(seg): bm.faces.new((A[k], A[(k + 1) % seg], B[(k + 1) % seg], B[k]))
    return put(role, _obj(bm), color, shade)

def finish(name):
    """Join parts per role, bake vertex colours, parent under an empty named after the prop."""
    root = bpy.data.objects.new(name, None); SC.collection.objects.link(root)
    for role, items in PARTS.items():
        for o, rgb in items:
            ca = o.data.color_attributes.new('Col', 'FLOAT_COLOR', 'CORNER')
            for d in ca.data: d.color = (*rgb, 1.)
            o.data.materials.append(MATS[role])
        bpy.ops.object.select_all(action='DESELECT')
        for o, _ in items: o.select_set(True)
        bpy.context.view_layer.objects.active = items[0][0]
        if len(items) > 1: bpy.ops.object.join()
        j = bpy.context.view_layer.objects.active; j.name = j.data.name = f'{name}_{role}'
        bpy.ops.object.shade_flat()
        j.parent = root
    PARTS.clear(); return root

# ======================= props =======================
CREAM, IRON, STONE_GREY = 0xf2ead8, 0x2b2b30, 0xb9b4aa

def building(floors, style):
    """6 m wide (x), 7.5 m deep (y), 3 m per floor; facade on +x like N.building."""
    W, D, H = 6., 7.5, floors * 3.
    fx = W / 2
    box('wall', (0, 0, H / 2), (W, D, H))
    box('wall', (fx + .01, 0, .35), (.06, D + .02, .7), shade=.72)                          # plinth
    for y in (-D / 2 + .18, D / 2 - .18):                                                     # corner pilasters
        box('wall', (fx + .06, y, H / 2), (.14, .36, H), shade=.9)
    for k in range(1, floors):                                                                # floor cornices
        box('fixed', (fx + .08, 0, k * 3), (.2, D + .1, .16), CREAM)
    box('fixed', (fx + .1, 0, H + .05), (.32, D + .3, .3), CREAM)                            # roof cornice
    box('wall', (0, 0, H + .45), (W, D, .6), shade=.86)                                       # parapet
    box('fixed', (0, 0, H + .78), (W + .1, D + .1, .08), CREAM)
    cols = [-2.5, 0., 2.5]
    for f in range(floors):
        z0 = f * 3
        for i, y in enumerate(cols):
            if f == 0 and i == 1:                                                             # shop / entrance
                box('glass', (fx + .02, y, 1.25), (.06, 1.7, 2.3), shade=.32)
                box('fixed', (fx + .05, y, 2.5), (.1, 1.95, .14), CREAM)
                for s in (-1, 1): box('fixed', (fx + .05, y + s * .92, 1.25), (.1, .12, 2.5), CREAM)
                for k in range(6):                                                            # striped awning
                    box('fixed', (fx + .55, y - .85 + k * .34 + .17, 2.62), (1.1, .34, .05),
                        0xd9542b if k % 2 == 0 else CREAM, rot=(0, -.32, 0))
                continue
            zc = z0 + 1.75
            box('fixed', (fx + .03, y, zc), (.08, 1.15, 1.7), CREAM)                         # frame
            box('glass', (fx + .07, y, zc), (.04, .9, 1.45), shade=.3)                       # pane
            if style == 'a':
                cyl('fixed', (fx + .03, y, zc + .72), .58, .08, CREAM, seg=16, rot=(0, math.pi / 2, 0))   # arch frame
                cyl('glass', (fx + .07, y, zc + .72), .45, .04, shade=.3, seg=16, rot=(0, math.pi / 2, 0))  # arched pane
                for s in (-1, 1):                                                             # open shutters
                    box('glass', (fx + .2, y + s * .78, zc), (.04, .44, 1.45), rot=(0, 0, s * .5))
                    for k in range(5):
                        box('glass', (fx + .23, y + s * .78, zc - .55 + k * .28), (.03, .4, .04), shade=.7, rot=(0, 0, s * .5))
            else:
                box('fixed', (fx + .1, y, zc - .78), (.2, 1.3, .08), CREAM)                  # sill
                box('glass', (fx + .09, y, zc + .12), (.03, .88, .9), shade=.85)              # half louvre
                for k in range(6):
                    box('glass', (fx + .11, y, zc - .25 + k * .14), (.02, .86, .03), shade=.55)
            if f > 0 and (style == 'b' or (i + f) % 2 == 0):                                  # balcony
                box('fixed', (fx + .35, y, z0 + .95), (.7, 1.5, .12), CREAM)
                box('fixed', (fx + .68, y, z0 + 1.85), (.04, 1.5, .05), IRON)
                box('fixed', (fx + .68, y, z0 + 1.08), (.04, 1.5, .04), IRON)
                for k in range(8):
                    box('fixed', (fx + .68, y - .7 + k * .2, z0 + 1.45), (.03, .03, .8), IRON)
                for s in (-1, 1):
                    box('fixed', (fx + .35, y + s * .74, z0 + 1.45), (.7, .03, .8), IRON)
            elif f > 0 and style == 'a' and (i + f) % 3 == 1:                                 # AC unit
                box('fixed', (fx + .25, y + .75, z0 + .7), (.5, .7, .45), 0xdcdcd6)
                cyl('fixed', (fx + .5, y + .75, z0 + .7), .17, .02, 0x777a80, seg=10, rot=(0, math.pi / 2, 0))
    # rooftop life: water tank, satellite dish, small stair hut
    cyl('fixed', (-1.2, -2.2, H + 1.4), .55, 1.1, 0xe8e6e0, seg=14)
    for a in range(4): box('fixed', (-1.2 + .35 * math.cos(a * 1.57), -2.2 + .35 * math.sin(a * 1.57), H + .62), (.06, .06, .5), IRON)
    sphere('fixed', (1.2, 2.3, H + 1.2), (.4, .4, .12), 0xf4f4f0, seg=12, rings=4)
    box('fixed', (1.2, 2.3, H + .95), (.05, .05, .5), IRON)
    if floors >= 4: box('wall', (-1.6, 1.8, H + 1.2), (1.6, 1.8, 1.8), shade=.8)
    return finish(f'building{floors}{style}')

def palm():
    H, lean = 5.2, .45
    pts = [Vector((lean * (t / H) ** 2, 0, t)) for t in [H * k / 14 for k in range(15)]]
    for k in range(14):                                                                       # ringed trunk
        a, b = pts[k], pts[k + 1]
        cyl('fixed', (a + b) / 2, .21 - k * .006, (b - a).length + .02, 0x8a5a2b if k % 2 else 0x9c6a36,
            r2=.17 - k * .006, seg=9, rot=(0, math.atan2(b.x - a.x, b.z - a.z), 0))
    top = pts[-1]
    sphere('fixed', top + Vector((0, 0, .05)), (.32, .32, .28), 0x6b4a22)
    for k in range(10):                                                                       # drooping fronds
        ang = k / 10 * 2 * math.pi + random.uniform(-.15, .15)
        d = Vector((math.cos(ang), math.sin(ang), 0)); L = random.uniform(2.3, 2.8)
        fp = [top + d * (L * t) + Vector((0, 0, .55 * math.sin(t * 2.2) - 1.1 * t * t)) for t in [i / 8 for i in range(9)]]
        w = [.15, .55, .75, .8, .75, .62, .45, .26, .04]
        strip('fixed', fp, w, 0x3f9a3a if k % 2 else 0x4fae45, shade=1.)
        strip('fixed', [p + Vector((0, 0, -.02)) for p in fp], [x * .35 for x in w], 0x2f7a2c)   # midrib
    for k in range(5):                                                                        # dates
        ang = k * 1.26
        sphere('fixed', top + Vector((.28 * math.cos(ang), .28 * math.sin(ang), -.32)), (.13, .13, .17), 0xd98a1f, seg=6, rings=4)
    return finish('palm')

def lamp():
    box('pole', (0, 0, .15), (.42, .42, .3), shade=.8, bevel=.03)
    cyl('pole', (0, 0, .45), .16, .3, shade=.9, r2=.1, seg=12)
    cyl('pole', (0, 0, 1.7), .085, 2.6, seg=10)
    for z in (.62, 1.2, 2.95): cyl('pole', (0, 0, z), .12, .07, shade=.85, seg=12)
    sphere('pole', (0, 0, 3.32), (.09, .09, .12), seg=10)
    for s in (-1, 1):                                                                         # scroll arms
        arm = [Vector((s * .55 * t, 0, 3.0 + .25 * math.sin(t * math.pi) + .1 * t)) for t in [i / 8 for i in range(9)]]
        tube('pole', arm, .035, seg=6)
        curl = [Vector((s * (.18 + .1 * math.cos(a)), 0, 2.85 + .1 * math.sin(a))) for a in [i * .7 for i in range(9)]]
        tube('pole', curl, .022, shade=.9, seg=5)
        x = s * .55
        cyl('pole', (x, 0, 3.27), .2, .14, r2=.04, seg=8)                                  # lantern roof
        for a in range(4):
            box('pole', (x + .14 * math.cos(a * 1.57 + .78), .14 * math.sin(a * 1.57 + .78), 3.0), (.025, .025, .4))
        cyl('pole', (x, 0, 2.78), .13, .05, seg=8)
        sphere('glow', (x, 0, 3.0), (.12, .12, .17), seg=10, rings=6)
    return finish('lamp')

def column():
    """Lotus column, 7 m like N.column(a=7); game scales y by a/7."""
    box('fixed', (0, 0, .3), (1.6, 1.6, .6), 0xd9b47a, bevel=.04)
    bm = bmesh.new(); seg, rings, Hs = 24, 10, 6.
    for j in range(rings + 1):                                                                # fluted papyrus shaft
        z = .6 + Hs * j / rings
        for k in range(seg):
            t = k / seg * 2 * math.pi
            r = (.62 - .08 * j / rings) * (1 + .05 * math.cos(seg / 2 * t))
            bm.verts.new((r * math.cos(t), r * math.sin(t), z))
    bm.verts.ensure_lookup_table()
    for j in range(rings):
        for k in range(seg):
            a, b = j * seg + k, j * seg + (k + 1) % seg
            bm.faces.new((bm.verts[a], bm.verts[b], bm.verts[b + seg], bm.verts[a + seg]))
    put('fixed', _obj(bm), 0xe4c48a)
    for i, (z, c) in enumerate(((1.5, 0x2f6fd8), (1.75, 0xc0392b), (2.0, 0x3fae4a), (5.6, 0x2f6fd8), (5.85, 0xc0392b))):
        cyl('fixed', (0, 0, z), .63 - (z - .6) * .013, .16, c, seg=24)
    for k in range(12):                                                                       # painted glyph tiles
        t = k / 12 * 2 * math.pi
        box('fixed', (.6 * math.cos(t), .6 * math.sin(t), 3.6 + (k % 3) * .55), (.06, .2, .3),
            (0x2f6fd8, 0xc0392b, 0x1f1f2a)[k % 3], rot=(0, 0, t))
    cyl('fixed', (0, 0, 6.95), .56, .9, 0xe4c48a, r2=1.0, seg=24)                           # lotus capital
    for k in range(8):
        t = k / 8 * 2 * math.pi
        box('fixed', (.8 * math.cos(t), .8 * math.sin(t), 7.0), (.08, .32, .85),
            0x3fae4a if k % 2 else 0x2f6fd8, rot=(0, -.45, t))
    box('fixed', (0, 0, 7.6), (1.85, 1.85, .4), 0xd9b47a, bevel=.03)
    return finish('column')

def cactus():
    """2.2 m saguaro like N.cactus (n = 1.6-2.8); game scales by n/2.2."""
    n = 2.2
    def ribbed(c, r, h):
        bm = bmesh.new(); seg = 16
        for j in range(5):
            z = c[2] - h / 2 + h * j / 4
            for k in range(seg):
                t = k / seg * 2 * math.pi; rr = r * (1 + .1 * (k % 2))
                bm.verts.new((c[0] + rr * math.cos(t), c[1] + rr * math.sin(t), z))
        bm.verts.ensure_lookup_table()
        for j in range(4):
            for k in range(seg):
                a, b = j * seg + k, j * seg + (k + 1) % seg
                bm.faces.new((bm.verts[a], bm.verts[b], bm.verts[b + seg], bm.verts[a + seg]))
        put('fixed', _obj(bm), 0x3f9a3f)
        sphere('fixed', (c[0], c[1], c[2] + h / 2), (r * 1.05, r * 1.05, r * .9), 0x45a845, seg=12, rings=6)
    ribbed((0, 0, n / 2), .27, n)
    for s, zb, h in ((1, n * .45, .75), (-1, n * .6, .55)):
        tube('fixed', [Vector((s * .2, 0, zb)), Vector((s * .45, 0, zb + .02)), Vector((s * .55, 0, zb + .2))], .15, 0x3f9a3f, seg=10)
        ribbed((s * .55, 0, zb + .2 + h / 2), .15, h)
    for k in range(5):
        t = k / 5 * 2 * math.pi
        sphere('fixed', (.1 * math.cos(t), .1 * math.sin(t), n + .25), (.08, .08, .05), 0xff6fa0, seg=6, rings=3)
    sphere('fixed', (0, 0, n + .26), (.05, .05, .05), 0xffe45a, seg=6, rings=3)
    return finish('cactus')

def rock(i):
    random.seed(30 + i)
    base = (0xc8783f, 0xb8692f, 0xd48a4f)
    for k in range(random.randint(3, 4)):                                                    # layered sandstone ledges
        w = random.uniform(1.6, 2.8) * (1 - k * .18)
        o = box('fixed', (random.uniform(-.3, .3), random.uniform(-.3, .3), .25 + k * .55),
                (w, w * random.uniform(.7, 1.1), .6), base[k % 3], shade=1 - k * .05, bevel=.12,
                rot=(0, 0, random.uniform(0, 3)))
        for v in o.data.vertices: v.co += Vector([random.uniform(-.08, .08) for _ in range(3)])
    ico('fixed', (random.uniform(-.8, .8), random.uniform(-.8, .8), .3), .45, 0xa85a28, jitter=.2, sub=1)
    return finish(f'rock{i}')

def tree():
    box('fixed', (0, 0, .2), (1.3, 1.3, .4), 0xa8acb4, bevel=.05)
    box('fixed', (0, 0, .39), (1.05, 1.05, .04), 0x5a3a22)
    cyl('fixed', (0, 0, 1.3), .14, 2.2, 0x7a5232, r2=.1, seg=8)
    for k in range(3):
        t = k * 2.1
        tube('fixed', [Vector((0, 0, 1.9)), Vector((.4 * math.cos(t), .4 * math.sin(t), 2.4))], .05, 0x7a5232, seg=5)
    for k, (c, r) in enumerate((((0, 0, 3.0), 1.1), ((.6, .3, 2.6), .75), ((-.5, -.4, 2.7), .8), ((.1, -.5, 3.5), .7), ((-.3, .5, 3.4), .7))):
        ico('fixed', c, r, 0x3f9a3a if k % 2 else 0x5cb84a, jitter=.15, sub=2)
    return finish('tree')

def stall():
    """Festival market stall like N.stall: counter along y, awning sloping to +x."""
    box('fixed', (0, 0, .5), (1.4, 2.6, 1.), 0x8a5a2b, bevel=.04)
    box('fixed', (.72, 0, .5), (.04, 2.4, .8), 0x6e4520)
    box('fixed', (0, 0, 1.03), (1.5, 2.7, .08), 0xa8743a)
    for s in (-1.2, 1.2):
        cyl('fixed', (.6, s, 1.75), .05, 2.5, 0x5a3a1c, seg=6)
        cyl('fixed', (-.6, s, 1.75), .05, 2.5, 0x5a3a1c, seg=6)
    for k in range(6):
        y = -1.25 + k * .5 + .25
        if k % 2: box('fixed', (.25, y, 2.85), (1.9, .5, .06), 0xffe8a8, rot=(0, .3, 0))
        else: box('awning', (.25, y, 2.85), (1.9, .5, .06), rot=(0, .3, 0))
    for k in range(6):
        box('awning' if k % 2 == 0 else 'fixed', (1.2, -1.25 + k * .5 + .25, 2.45), (.04, .5, .3), 0xffe8a8, rot=(0, .3, 0))
    fruit = (0xffb21a, 0xff5a3a, 0x3fd06a, 0xff8a3d)
    for k in range(10):
        sphere('fixed', (random.uniform(-.4, .45), -1.05 + k * .23, 1.17), (.11, .11, .11), fruit[k % 4], seg=8, rings=5)
    sphere('glow', (.7, 0, 2.2), (.16, .16, .22), seg=10, rings=6)                           # lantern
    cyl('fixed', (.7, 0, 2.47), .14, .1, 0xc8962a, r2=.03, seg=8)
    cyl('fixed', (.7, 0, 1.95), .1, .05, 0xc8962a, seg=8)
    return finish('stall')

def tower(h):
    """Glass tower like N.skyscraper: 7.5 m square, height h; game scales to the real n x i."""
    W = 7.5; hw = W / 2
    box('wall', (0, 0, h / 2), (W, W, h))                                                    # tinted curtain glass
    for k in range(1, int(h // 3)):                                                           # floor slabs
        box('fixed', (0, 0, k * 3), (W + .12, W + .12, .22), 0xe8f4ff)
    for s in (-1, 1):                                                                         # mullion fins, all four faces
        for j in range(6):
            t = -hw + .75 + j * 1.2
            box('fixed', (s * (hw + .06), t, h / 2), (.12, .1, h), 0xcfd8e4)
            box('fixed', (t, s * (hw + .06), h / 2), (.1, .12, h), 0xcfd8e4)
    box('wall', (0, 0, .9), (W + .05, W + .05, 1.8), shade=.55)                               # dark lobby band
    box('fixed', (hw + .5, 0, 1.9), (1.0, 3.2, .12), 0xcfd8e4)                                # entrance canopy
    box('fixed', (0, 0, h + .5), (W - 1.2, W - 1.2, 1.0), 0x3a4252)                          # crown
    box('wall', (0, 0, h + 1.3), (W - 2.4, W - 2.4, .6), shade=.8)
    cyl('fixed', (0, 0, h + 3.3), .12, 3.4, 0xd8d8d8, seg=6)                                  # antenna
    sphere('glow', (0, 0, h + 5.05), (.18, .18, .18), seg=8, rings=5)
    return finish(f'tower{int(h)}')

PROPS = [building(n, s) for n in range(2, 7) for s in 'ab'] + [palm(), lamp(), column(), cactus(), rock(1), rock(2), rock(3), tree(), stall()] \
      + [tower(h) for h in (21, 30, 39)]
for o in SC.objects:
    if o.type == 'MESH': print('PROP', o.name, len(o.data.polygons))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'world_props.blend'))
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, 'world_props.glb'), export_format='GLB', export_yup=True,
                          export_apply=True, export_vertex_color='ACTIVE', export_draco_mesh_compression_enable=True,
                          export_draco_mesh_compression_level=7, export_draco_color_quantization=8)

if DO_RENDER:  # contact sheet with sample palettes so the props can be judged before going in the game
    import itertools
    tint = {'wall': 0xe8c9a0, 'glass': 0x2f6fb5, 'pole': 0x2f2f3a, 'awning': 0xd9542b, 'glow': 0xffe08a}
    for o in SC.objects:
        if o.type != 'MESH': continue
        role = o.name.rsplit('_', 1)[1]
        if role in tint:
            m = MATS[role].copy(); o.data.materials[0] = m
            nt = m.node_tree; b = nt.nodes['Principled BSDF']
            mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'; mix.inputs['Factor'].default_value = 1
            mix.inputs['B'].default_value = (*lin(tint[role]), 1)
            nt.links.new(nt.nodes['Color Attribute'].outputs['Color'], mix.inputs['A'])
            nt.links.new(mix.outputs['Result'], b.inputs['Base Color'])
            if role == 'glow': b.inputs['Emission Strength'].default_value = 4
    x = 0
    for root in PROPS:
        root.location = (x, 0, 0); root.rotation_euler = (0, 0, -math.pi / 2)   # +x front -> faces the camera (-y)
        x += 9 if root.name.startswith('building') else 4
    r = SC.render; r.engine = 'CYCLES'; SC.cycles.device = 'CPU'; SC.cycles.samples = 24; SC.cycles.use_denoising = True
    r.resolution_x, r.resolution_y = 2400, 700; SC.view_settings.view_transform = 'AgX'
    w = bpy.data.worlds.new('w'); SC.world = w; w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (*lin(0x9fd0ff), 1); w.node_tree.nodes['Background'].inputs['Strength'].default_value = .8
    bpy.ops.mesh.primitive_plane_add(size=400); g = bpy.context.active_object
    gm = bpy.data.materials.new('g'); gm.use_nodes = True; gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (*lin(0xd8c8a8), 1); g.data.materials.append(gm)
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sun.data.energy = 3.5; sun.rotation_euler = (.8, .2, -.6); SC.collection.objects.link(sun)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); SC.collection.objects.link(cam); SC.camera = cam
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = x + 4
    cam.location = (x / 2 - 3, -60, 14); cam.rotation_euler = (math.radians(80), 0, 0)
    r.filepath = os.path.join(OUT, 'world-props.png'); bpy.ops.render.render(write_still=True)
