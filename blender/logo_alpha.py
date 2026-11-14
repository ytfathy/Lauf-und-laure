# Cut the round International Education Egypt logo out of its black background.
# Usage: blender -b --factory-startup -P logo_alpha.py -- <in.jpg> <out.png> <out_small.webp>
import bpy, sys, numpy as np
src, out_png, out_small = sys.argv[sys.argv.index('--') + 1:][:3]
im = bpy.data.images.load(src); w, h = im.size
px = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)
lum = px[..., :3].max(axis=2)
# circle centre/radius from the first non-black pixels on the middle row and column
row, col = lum[h // 2], lum[:, w // 2]
xs, ys = np.nonzero(row > .06)[0], np.nonzero(col > .06)[0]
cx, cy = (xs[0] + xs[-1]) / 2, (ys[0] + ys[-1]) / 2
r = min(xs[-1] - xs[0], ys[-1] - ys[0]) / 2 - 1.5
yy, xx = np.mgrid[0:h, 0:w]
d = np.hypot(xx - cx, yy - cy)
px[..., 3] = np.clip(r - d + .5, 0, 1)          # 1px anti-aliased edge
assert px[h // 2, w // 2, 3] == 1 and px[0, 0, 3] == 0
print('CIRCLE', cx, cy, r)
im = bpy.data.images.new('logo', w, h, alpha=True); im.pixels[:] = px.ravel()
im.filepath_raw = out_png; im.file_format = 'PNG'; im.save()
im.scale(256, 256); im.filepath_raw = out_small; im.file_format = 'WEBP'; im.save()
