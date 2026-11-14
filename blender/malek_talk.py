# Run with Malek - talking-head frames for the checkpoint read-aloud.
# Usage: blender -b malek.blend -P malek_talk.py -- <out_dir>
# Renders Malek's face with 4 mouth shapes (closed smile, small, wide, round) as transparent WEBP.
import bpy, sys, os
from mathutils import Vector
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else os.getcwd())
os.makedirs(OUT, exist_ok=True)
SC = bpy.context.scene

def lin(h):
    c = [((h >> s) & 255) / 255 for s in (16, 8, 0)]
    return tuple(x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4 for x in c)

def mat(name, hexc, rough=.6):
    m = bpy.data.materials.new(name); m.use_nodes = True
    I = m.node_tree.nodes['Principled BSDF'].inputs
    I['Base Color'].default_value = (*lin(hexc), 1); I['Roughness'].default_value = rough
    return m

head = bpy.data.objects['head']
bvh = BVHTree.FromObject(head, bpy.context.evaluated_depsgraph_get())
def surf(x, z):
    hit = bvh.ray_cast(Vector((x, -2, z)), Vector((0, 1, 0)))[0]
    return hit.y if hit else -.28

M_IN = mat('mouthIn', 0x4a1218, .7)
M_TEETH = mat('teeth', 0xfbfbf6, .35)
M_TONGUE = mat('tongue', 0xe2626e, .5)

def ellipsoid(name, m, loc, size):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, location=loc)
    o = bpy.context.active_object; o.name = name; o.scale = size
    bpy.ops.object.shade_smooth(); o.data.materials.append(m); return o

def mouth(w, h, z0=1.358):
    y = surf(0, z0)
    objs = [ellipsoid('mOpen', M_IN, (0, y + .004, z0), (w, .014, h))]
    objs.append(ellipsoid('mTeeth', M_TEETH, (0, y - .0005, z0 + h * .62), (w * .78, .009, h * .3)))
    objs.append(ellipsoid('mTongue', M_TONGUE, (0, y + .001, z0 - h * .5), (w * .6, .01, h * .38)))
    return objs

smile = [o for o in bpy.data.objects if o.name.split('.')[0] in ('smile', 'smileCorner')]
M_SMILE = smile[0].data.materials[0]
for o in smile:   # own mesh copies so the material swap stays local
    o.data = o.data.copy()

# ---- render setup (same look as malek.py face shot, transparent background) ----
r = SC.render; r.engine = 'CYCLES'; SC.cycles.device = 'CPU'; SC.cycles.samples = 32; SC.cycles.use_denoising = True
r.resolution_x = r.resolution_y = 360; r.film_transparent = True
r.image_settings.file_format = 'WEBP'; r.image_settings.color_mode = 'RGBA'; r.image_settings.quality = 88
SC.view_settings.view_transform = 'AgX'; SC.view_settings.look = 'AgX - Punchy'
w = bpy.data.worlds.new('w'); SC.world = w; w.use_nodes = True
bg = w.node_tree.nodes['Background']; bg.inputs['Color'].default_value = (*lin(0x1d3c9e), 1); bg.inputs['Strength'].default_value = .6
def area(name, loc, power, size, color, target=(0, 0, .9)):
    L = bpy.data.lights.new(name, 'AREA'); L.energy = power; L.size = size; L.color = lin(color)
    o = bpy.data.objects.new(name, L); o.location = loc; SC.collection.objects.link(o)
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
area('key', (2.2, -3, 3.2), 520, 2.5, 0xfff0dc)
area('fill', (-3, -2, 1.6), 140, 3, 0xcfe0ff)
area('rim', (-1.5, 3, 2.8), 700, 2, 0xa8d4ff)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); SC.collection.objects.link(cam); SC.camera = cam
cam.location = (.25, -2.2, 1.5); cam.data.lens = 80
cam.rotation_euler = (Vector((0, 0, 1.47)) - cam.location).to_track_quat('-Z', 'Y').to_euler()

FRAMES = [('closed', None), ('small', (.05, .024)), ('wide', (.062, .046)), ('round', (.036, .042))]
for name, shape in FRAMES:
    extra = []
    for o in smile:   # open mouth: the smile tube turns skin-coloured and fills the carved crease
        o.data.materials[0] = head.data.materials[0] if shape else M_SMILE
        o.scale = (1, 1, 1)
    if shape: extra = mouth(*shape)
    r.filepath = os.path.join(OUT, 'malek-talk-' + name + '.webp')
    bpy.ops.render.render(write_still=True); print('RENDERED', name)
    for o in extra: bpy.data.objects.remove(o, do_unlink=True)
