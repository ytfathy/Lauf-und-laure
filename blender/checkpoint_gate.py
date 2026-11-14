# Run with Malek - checkpoint gate (question gate placed on the track).
# Usage: blender -b --factory-startup -P checkpoint_gate.py -- <out_dir> [render]
# Blender Z-up, front faces -Y (= +Z in glTF = towards the game camera).
# Track: 3 lanes at x = -2.4 / 0 / 2.4; the arch clears trains (inner height 6 m, inner width 8.6 m).
import bpy, bmesh, math, sys, os
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else os.getcwd())
DO_RENDER = len(argv) > 1 and argv[1] == 'render'
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
SC = bpy.context.scene

def lin(h):
    c = [((h >> s) & 255) / 255 for s in (16, 8, 0)]
    return tuple(x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4 for x in c)

def mat(name, hexc, rough=.6, metal=0., emit=0.):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']; I = b.inputs
    I['Base Color'].default_value = (*lin(hexc), 1); I['Roughness'].default_value = rough; I['Metallic'].default_value = metal
    if emit: I['Emission Color'].default_value = (*lin(hexc), 1); I['Emission Strength'].default_value = emit
    return m

STONE = mat('stone', 0xe7bd76, .8)
STONE_D = mat('stoneDark', 0xc28c47, .85)
BLUE = mat('lapis', 0x1f5fd0, .35)
GOLD = mat('gold', 0xffc21c, .3, metal=.9)
GLOW = mat('glow', 0xffe45a, .4, emit=3.)
GLOW_B = mat('glowBlue', 0x5cc2ff, .4, emit=2.5)

PARTS = []
def box(name, m, loc, size, bevel=.06):
    bpy.ops.mesh.primitive_cube_add(location=loc); o = bpy.context.active_object; o.name = name
    o.scale = (size[0] / 2, size[1] / 2, size[2] / 2); bpy.ops.object.transform_apply(scale=True)
    if bevel:
        md = o.modifiers.new('b', 'BEVEL'); md.width = bevel; md.segments = 2
    o.data.materials.append(m); PARTS.append(o); return o

def cyl(name, m, loc, r1, r2, h, verts=24, rot=None):
    bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r1, radius2=r2, depth=h, location=loc)
    o = bpy.context.active_object; o.name = name
    if rot: o.rotation_euler = rot
    bpy.ops.object.shade_smooth(); o.data.materials.append(m); PARTS.append(o); return o

def text(name, m, s, loc, size, depth=.08):
    bpy.ops.object.text_add(location=loc); o = bpy.context.active_object; o.name = name
    o.data.body = s; o.data.size = size; o.data.extrude = depth; o.data.align_x = 'CENTER'; o.data.align_y = 'CENTER'
    o.rotation_euler = (math.pi / 2, 0, 0)
    bpy.ops.object.convert(target='MESH'); o.data.materials.append(m); PARTS.append(o); return o

# ---- pillars: tapered sandstone with lapis/gold bands and lotus capitals ----
for s in (-1, 1):
    x = s * 4.9
    box('base', STONE_D, (x, 0, .3), (1.5, 1.5, .6))
    cyl('shaft', STONE, (x, 0, 3.3), .62, .5, 5.4, verts=20)
    for z in (1.1, 1.35, 5.3):
        cyl('band', BLUE if z != 1.35 else GOLD, (x, 0, z), .66 - z * .02, .66 - z * .02, .14, verts=20)
    cyl('lotus', GOLD, (x, 0, 6.25), .52, .82, .5, verts=20)          # bell capital
    box('abacus', STONE_D, (x, 0, 6.6), (1.3, 1.3, .2))
    # glowing blue light strip facing the runner
    box('strip', GLOW_B, (x, -.56, 3.2), (.14, .06, 3.6), bevel=.02)

# ---- lintel with cavetto cornice ----
box('lintel', STONE, (0, 0, 7.1), (11.6, 1.2, .9))
box('cornice', STONE_D, (0, -.05, 7.75), (12.2, 1.45, .4))
box('frieze', BLUE, (0, -.62, 7.1), (10.4, .06, .5), bevel=.02)
text('label', GLOW, 'CHECKPOINT', (0, -.68, 7.08), .48, depth=.04)

# ---- winged sun disc with the big question mark ----
cyl('sun', GOLD, (0, -.1, 8.95), 1.15, 1.15, .3, verts=40, rot=(math.pi / 2, 0, 0))
cyl('sunFace', BLUE, (0, -.27, 8.95), .95, .95, .06, verts=40, rot=(math.pi / 2, 0, 0))
text('q', GLOW, '?', (0, -.33, 8.92), 1.5, depth=.08)
for s in (-1, 1):
    for i, (w, h, dz) in enumerate(((2.2, .34, .35), (1.9, .3, 0), (1.5, .26, -.33))):
        wing = box('wing', GOLD if i % 2 == 0 else BLUE, (s * (1.15 + w / 2), -.05, 8.95 + dz), (w, .18, h), bevel=.04)
        wing.rotation_euler = (0, s * -.12, 0)

# ---- ground line: glowing strip across all lanes so kids see where the question starts ----
box('line', GLOW, (0, 0, .03), (9.0, .35, .06), bevel=.0)

for o in PARTS:
    o.select_set(True)
bpy.context.view_layer.objects.active = PARTS[0]
for o in PARTS:
    bpy.context.view_layer.objects.active = o
    for md in list(o.modifiers): bpy.ops.object.modifier_apply(modifier=md.name)
bpy.ops.object.select_all(action='SELECT')
bpy.context.view_layer.objects.active = PARTS[0]
bpy.ops.object.join(); gate = bpy.context.active_object; gate.name = 'checkpointGate'
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
print('FACES', len(gate.data.polygons))

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'checkpoint_gate.blend'))
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, 'checkpoint_gate.glb'), export_format='GLB',
                          export_apply=True, export_yup=True, use_selection=False)

if DO_RENDER:
    r = SC.render; r.engine = 'CYCLES'; SC.cycles.device = 'CPU'; SC.cycles.samples = 32; SC.cycles.use_denoising = True
    r.resolution_x, r.resolution_y = 1000, 800
    SC.view_settings.view_transform = 'AgX'
    w = bpy.data.worlds.new('w'); SC.world = w; w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (*lin(0x8fc9ff), 1)
    bpy.ops.mesh.primitive_plane_add(size=40); g = bpy.context.active_object; g.data.materials.append(mat('sand', 0xd9b27a, .9))
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sun.data.energy = 4; sun.rotation_euler = (.9, .2, .6)
    SC.collection.objects.link(sun)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); SC.collection.objects.link(cam); SC.camera = cam
    cam.location = (3, -22, 5); cam.data.lens = 40
    cam.rotation_euler = (Vector((0, 0, 4.5)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    r.filepath = os.path.join(OUT, 'checkpoint-gate.png'); bpy.ops.render.render(write_still=True)
