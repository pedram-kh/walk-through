"""Stop 01, hero - layout pass (Blender 4.5 LTS, CPU render).

Builds flat tiles (photo + galaxy) and galaxy dust, renders a preview, and
exports the browser assets.
Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python stops/01-hero/build.py
Outputs beside this file:
  poster.jpg, stop.blend     preview render (also the fallback poster) and editable scene
  stop.glb                   the tiles (names, sizes, rest transforms)
  dust.bin                   dust points: x y z r g b size owner (float32 x 8)
  flow.bin                   current particles: path t radius angle jitter*2 size r g b seed (float32 x 11)
  stop.json                  contract: rest camera, brief, palette, tiles, dust, flow
"""
import bpy, json, math, random, struct
from pathlib import Path
from mathutils import Vector, Euler, Matrix

OUT = Path(__file__).resolve().parent

# What was agreed for this stop (the five content questions), kept in stop.json.
BRIEF = {
    'status': 'approved 2026-10-03',
    'text': 'HTML over the scene: headline, subline, Strategy/Production/Performance/Scale list. '
            'HTML captions that ride on tiles: UGC, Motion, Static, Design, Hi-Fi.',
    'buttons': "HTML 'Let's talk' pill under the subline, links to catalyst-growth.com/contact. "
               'Top bar (page level): logo, five-diamond menu icon.',
    'button_behaviour': 'Part of the section HTML: scrolls away with the curtain.',
    'scene_behaviour': 'Idle: tiles bob, dust twinkles, the particle current flows, three videos play. '
                       'Cursor: tiles near it tilt and lift, dust and current part around it. '
                       'Leaving: freezes and turns black and white at the first scroll movement.',
    'media': '19 photos on tiles (8 colour, 11 tinted on galaxy tiles), videos on hero, portrait and product tiles.',
    'exceptions': 'three playing videos; size above 2 MB (agreed 2026-10-03)',
}
SEED = 7

# ---- Palette (sampled from the Catalyst reference artwork; edit here) -------
def hex_rgb(h):
    h = h.lstrip('#')
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb)

PALETTE = {
    'background': hex_rgb('#020204'),
    'violet': hex_rgb('#a14fe2'),
    'violet_bright': hex_rgb('#bd71f6'),
    'blue': hex_rgb('#4d6ab1'),
    'blue_bright': hex_rgb('#6e8aef'),
    'teal': hex_rgb('#2398af'),
    'teal_bright': hex_rgb('#59c6e7'),
}

# ---- Perspective wall ---------------------------------------------------------
# Tiles face along a wall that recedes from near-right to far-left; the wall
# sets their yaw and the direction of the dust streams.
WALL_FAR = (-8.5, 4.0)      # far end, left of frame
WALL_NEAR = (5.2, -2.5)      # near end, right of frame
CAMERA_AT = (0.0, -11.0, -0.2)
CAMERA_LENS = 28             # wide lens = stronger perspective
FRAME = (1616, 875)          # design frame (render size); the browser keeps this framing

# ---- Tiles ------------------------------------------------------------------
# Placed by where they land in the design frame: x, y = tile centre (0..1 from
# the top-left), size = tile height as a fraction of the frame height. Depth
# follows from size, so a smaller size pushes the tile further back.
# w/h: size in scene units (the images are cropped to this shape),
# turn: extra yaw in degrees (0 = along the wall), roll in degrees.
# The copy sits on the left, so the cluster keeps to the right of x = 0.36.
# kind 'photo'  = images/<label>.jpg (videos/<label>-poster.jpg on video tiles);
#                 if missing, a placeholder whose look is a grey value or a palette name
# kind 'galaxy' = tinted tile with printed dust; look is a palette name. If
#                 images/<label>.jpg exists it shows through in that one colour
# Spacing: positions below (tiles and current paths) are spread from CLUSTER_CENTRE
# by SPACING relative to tile size, then everything is scaled by TILE_SCALE so the
# cluster keeps its footprint. 1.3 / 0.85 = 30% more room between smaller tiles.
CLUSTER_CENTRE = (0.69, 0.60)
SPACING = 1.3
TILE_SCALE = 0.85


def spread(x, y):
    k = SPACING * TILE_SCALE
    return CLUSTER_CENTRE[0] + (x - CLUSTER_CENTRE[0]) * k, CLUSTER_CENTRE[1] + (y - CLUSTER_CENTRE[1]) * k


TILES = [
    # label,         kind,     x,     y,     w,   h,    size,  turn, roll, look
    ('hero',         'photo',  0.822, 0.350, 2.4, 3.3,  0.280,  -4,   -2,  0.78),      # MOTION slot
    ('portrait',     'photo',  0.666, 0.520, 2.9, 2.2,  0.325,  10,    0,  'violet'),  # large centre
    ('texture',      'photo',  0.451, 0.720, 2.0, 1.7,  0.184,  10,    1,  0.50),      # DESIGN
    ('landscape',    'photo',  0.646, 0.767, 3.0, 1.4,  0.150,  10,    0,  0.34),      # bottom centre
    ('statement',    'photo',  0.918, 0.547, 2.2, 2.0,  0.206,   4,    0,  0.10),      # STATIC
    ('card',         'photo',  0.863, 0.829, 2.2, 1.10, 0.150,   2,   -2,  0.70),      # HI-FI
    ('product',      'photo',  0.490, 0.533, 1.8, 1.20, 0.145,  10,    0,  0.38),      # UGC
    ('splash',       'photo',  0.796, 0.648, 1.3, 0.95, 0.179,   8,    0,  0.55),      # IDEAS TESTED
    ('ugc',          'galaxy', 0.364, 0.693, 1.9, 1.9,  0.130,  10,    0,  'violet'),
    ('far_left',     'galaxy', 0.326, 0.775, 3.5, 1.1,  0.076,  10,    0,  'violet'),
    ('behind_hero',  'galaxy', 0.660, 0.430, 4.2, 2.0,  0.200,  10,    0,  'blue'),
    ('top_violet',   'galaxy', 0.990, 0.206, 2.0, 1.6,  0.130,   6,    2,  'violet'),
    ('top_teal',     'galaxy', 0.945, 0.325, 3.6, 1.5,  0.113,   6,    2,  'teal'),
    ('right_blue',   'galaxy', 0.505, 0.477, 1.7, 0.9,  0.090,  10,    0,  'blue'),
    ('side_strip',   'galaxy', 0.423, 0.607, 1.2, 2.0,  0.162,  10,    0,  'blue'),
    ('mid_violet',   'galaxy', 0.862, 0.640, 1.8, 0.8,  0.060,   6,    0,  'violet'),
    ('right_teal',   'galaxy', 0.980, 0.650, 1.8, 1.8,  0.162,   6,    0,  'teal'),
    ('floor_teal',   'galaxy', 0.757, 0.856, 3.0, 0.9,  0.092,  10,   -2,  'teal'),
    ('floor_streak', 'galaxy', 0.622, 0.883, 3.8, 0.75, 0.054,  10,   -3,  'blue'),
]

# ---- Particle current ---------------------------------------------------------
# Fine fibres of particles that wind through the cluster and wrap around tiles.
# Paths are control points placed like the tiles: (x, y) in the frame and a depth
# from the camera. Deeper than a tile = behind it, shallower = in front, so
# alternating depths wrap the current around a tile. Particles flow from the first
# point to the last and fade at both ends; the current ends before the copy.
# Tile depths (before TILE_SCALE, which scales both alike): splash 7.6, portrait (centre) 9.7, card (Hi-Fi) 10.5, product (UGC)
# 11.9, texture (Design) 13.3, landscape 13.4, statement (Static) 14.0, hero (Motion) 16.9
MAIN_PATH = [
    (1.10, 0.05, 12.0),    # in from the top right
    (0.93, 0.17, 13.0),    # in front of Motion's top corner
    (0.83, 0.34, 18.5),    # behind Motion
    (0.74, 0.30, 15.0),    # out past its left edge
    (0.60, 0.31, 11.5),    # along the top of the centre tile, behind it
    (0.525, 0.50, 10.6),   # down its left side, between it and UGC
    (0.62, 0.72, 8.6),     # round its bottom edge, in front
    (0.52, 0.68, 11.0),    # in front of Design
    (0.455, 0.808, 15.0),  # behind Design, along its bottom
    (0.399, 0.690, 17.0),  # out into the gap between Design and the purple square
    (0.364, 0.614, 18.0),  # over the square's top, in front
    (0.319, 0.700, 23.0),  # down its left side, behind
    (0.382, 0.742, 22.0),  # back through the gap between the square and the strip
    (0.328, 0.835, 19.0),  # under the strip, in front
    (0.247, 0.872, 22.0),  # fading out to the bottom left
]
STATIC_PATH = [
    (1.10, 0.40, 11.5),
    (0.97, 0.42, 12.5),    # over Static's top corner, in front
    (0.90, 0.56, 17.0),    # behind Static
    (0.84, 0.71, 12.0),    # out below it
    (0.71, 0.74, 9.8),     # joins the main current under the centre tile
] + MAIN_PATH[6:]
HIFI_PATH = [
    (1.10, 0.97, 9.0),
    (0.97, 0.86, 9.6),     # in front of Hi-Fi's right end
    (0.87, 0.96, 12.0),    # under it
    (0.77, 0.83, 11.6),    # behind its left end
    (0.70, 0.77, 9.6),     # joins the main current
] + MAIN_PATH[6:]
FLOWS = [
    # path,       particles, width, fibres, speed (units/s)
    (MAIN_PATH,   9000,      0.196, 34,     0.48),
    (STATIC_PATH, 3000,      0.098, 16,     0.42),
    (HIFI_PATH,   3000,      0.098, 16,     0.42),
]
FLOW_AMOUNT = 1.8        # scales the particle counts above (strength of the current)
FLOW_TWIST = 9.0         # radians the fibres wind around their path, end to end
FLOW_SAMPLES = 160       # points per path sent to the browser
FLOW_COLOR = ('#a4a4aa', '#e2e2e6')      # light grey, a touch brighter than the dust

DUST_AMOUNT = 0.5        # scales the dust printed on galaxy tiles
DUST_PER_AREA = 950      # dust points per square unit of galaxy tile
DUST_RADIUS = 0.0055
# Dust colour: (base, bright) hex, or None to tint each point with its tile/stream colour
DUST_COLOR = ('#9a9aa0', '#d0d0d4')      # light grey

WALL_DIR = Vector((WALL_NEAR[0] - WALL_FAR[0], WALL_NEAR[1] - WALL_FAR[1])).normalized()
WALL_YAW = math.degrees(math.atan2(WALL_DIR.y, WALL_DIR.x))
WALL_FRONT = Vector((WALL_DIR.y, -WALL_DIR.x))    # points toward the camera side

# glTF and Three.js use Y up, so Blender (x, y, z) becomes (x, z, -y).
def y_up(v):
    return [round(v[0], 5), round(v[2], 5), round(-v[1], 5)]


# ---- Scene ------------------------------------------------------------------
random.seed(SEED)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
tiles_col = bpy.data.collections.new('Tiles')
dust_col = bpy.data.collections.new('Dust')
scene.collection.children.link(tiles_col)
scene.collection.children.link(dust_col)

# Camera first: tiles and streams are placed through it.
scene.render.resolution_x, scene.render.resolution_y = FRAME
cam_data = bpy.data.cameras.new('Hero camera')
cam_data.lens = CAMERA_LENS
camera = bpy.data.objects.new('Hero camera', cam_data)
scene.collection.objects.link(camera)
camera.location = CAMERA_AT
target = Vector((CAMERA_AT[0], 0, 0))
camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = camera
bpy.context.view_layer.update()
_frame = [Vector(c) / -c[2] for c in cam_data.view_frame(scene=scene)]   # frame corners at depth 1
FRAME_LEFT, FRAME_RIGHT = min(c.x for c in _frame), max(c.x for c in _frame)
FRAME_TOP, FRAME_BOTTOM = max(c.y for c in _frame), min(c.y for c in _frame)


def screen_point(x, y, depth):
    """World point that lands at (x, y) in the frame (0..1 from top-left), depth units ahead."""
    local = Vector((FRAME_LEFT + x * (FRAME_RIGHT - FRAME_LEFT),
                    FRAME_TOP + y * (FRAME_BOTTOM - FRAME_TOP), -1)) * depth
    return camera.matrix_world @ local


def emission_material(name, color, strength=1.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    out = nodes.new('ShaderNodeOutputMaterial')
    em = nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (*color, 1)
    em.inputs['Strength'].default_value = strength
    links.new(em.outputs['Emission'], out.inputs['Surface'])
    return mat, em


GALAXY_PHOTO = 0.85      # how strongly a galaxy tile's photo shows (matches CONFIG.galaxyPhoto)


def galaxy_material(name, tint, bright, photo=None):
    """Dark tinted tile with a fine printed sparkle pattern, over an optional
    one-colour photo (shadows -> deep tint, highlights -> bright tint)."""
    mat, em = emission_material(name, tint)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    coord = nodes.new('ShaderNodeTexCoord')
    cells = nodes.new('ShaderNodeTexVoronoi')
    cells.inputs['Scale'].default_value = 70
    dots = nodes.new('ShaderNodeValToRGB')
    dots.color_ramp.elements[0].position = 0.0
    dots.color_ramp.elements[0].color = (1, 1, 1, 1)
    dots.color_ramp.elements[1].position = 0.16
    dots.color_ramp.elements[1].color = (0, 0, 0, 1)
    cloud = nodes.new('ShaderNodeTexNoise')
    cloud.inputs['Scale'].default_value = 2.2
    cloud.inputs['Detail'].default_value = 5
    wash = nodes.new('ShaderNodeMixRGB')          # dark base -> tint, by cloud
    wash.inputs['Color1'].default_value = (*(c * 0.06 for c in tint), 1)
    wash.inputs['Color2'].default_value = (*(c * 0.55 for c in tint), 1)
    spark = nodes.new('ShaderNodeMixRGB')         # add bright dots on top
    spark.inputs['Color2'].default_value = (*bright, 1)
    links.new(coord.outputs['UV'], cells.inputs['Vector'])
    links.new(coord.outputs['UV'], cloud.inputs['Vector'])
    links.new(cells.outputs['Distance'], dots.inputs['Fac'])
    links.new(cloud.outputs['Fac'], wash.inputs['Fac'])
    base = wash.outputs['Color']
    if photo:
        tex = nodes.new('ShaderNodeTexImage')
        tex.image = bpy.data.images.load(str(photo))
        tex.extension = 'EXTEND'
        grey = nodes.new('ShaderNodeRGBToBW')
        lum = nodes.new('ShaderNodeMath')              # perceptual-ish lightness
        lum.operation = 'POWER'
        lum.inputs[1].default_value = 0.5
        tone = nodes.new('ShaderNodeMixRGB')           # deep tint -> bright tint
        tone.inputs['Color1'].default_value = (*(c * 0.55 for c in tint), 1)
        tone.inputs['Color2'].default_value = (*(c * 0.8 for c in bright), 1)
        lift = nodes.new('ShaderNodeMapRange')
        lift.interpolation_type = 'SMOOTHSTEP'
        lift.inputs['From Min'].default_value, lift.inputs['From Max'].default_value = 0.05, 0.75
        duo = nodes.new('ShaderNodeMixRGB')            # near-black shadows
        duo.inputs['Color1'].default_value = (*(c * 0.03 for c in tint), 1)
        over = nodes.new('ShaderNodeMixRGB')           # photo over the cloud wash
        over.inputs['Fac'].default_value = GALAXY_PHOTO
        links.new(tex.outputs['Color'], grey.inputs['Color'])
        links.new(grey.outputs['Val'], lum.inputs[0])
        links.new(lum.outputs['Value'], tone.inputs['Fac'])
        links.new(lum.outputs['Value'], lift.inputs['Value'])
        links.new(lift.outputs['Result'], duo.inputs['Fac'])
        links.new(tone.outputs['Color'], duo.inputs['Color2'])
        links.new(wash.outputs['Color'], over.inputs['Color1'])
        links.new(duo.outputs['Color'], over.inputs['Color2'])
        base = over.outputs['Color']
    links.new(base, spark.inputs['Color1'])
    links.new(dots.outputs['Color'], spark.inputs['Fac'])
    links.new(spark.outputs['Color'], em.inputs['Color'])
    return mat


def photo_file(label):
    """The real photo for a tile: the video poster on video tiles, else the image."""
    for path in (OUT / 'media' / 'videos' / f'{label}-poster.jpg', OUT / 'media' / 'images' / f'{label}.jpg'):
        if path.exists():
            return path
    return None


def photo_material(name, path):
    """Emits the photo at its own colours, so the preview shows the real image."""
    mat, em = emission_material(name, (1, 1, 1))
    tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
    tex.image = bpy.data.images.load(str(path))
    tex.extension = 'EXTEND'
    mat.node_tree.links.new(tex.outputs['Color'], em.inputs['Color'])
    return mat


def make_tile(index, label, kind, x, y, w, h, size, turn, roll, look):
    x, y = spread(x, y)
    depth = h / (size * TILE_SCALE * (FRAME_TOP - FRAME_BOTTOM))      # apparent height -> distance
    yaw = WALL_YAW + turn
    name = f'Tile_{index:02d}_{kind}'
    mesh = bpy.data.meshes.new(name)
    hw, hh = w / 2, h / 2
    mesh.from_pydata([(-hw, 0, -hh), (hw, 0, -hh), (hw, 0, hh), (-hw, 0, hh)], [], [(0, 1, 2, 3)])
    uv = mesh.uv_layers.new(name='UVMap')
    for loop, co in zip(uv.data, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        loop.uv = co
    ob = bpy.data.objects.new(name, mesh)
    ob.location = screen_point(x, y, depth)
    ob.rotation_euler = Euler((0, math.radians(roll), math.radians(yaw)), 'XYZ')
    ob['label'], ob['kind'] = label, kind
    photo = photo_file(label) if kind == 'photo' else None
    if photo:
        mat = photo_material(f'Photo {label}', photo)
    elif kind == 'photo' and isinstance(look, str):     # colour-graded photo
        mat, _ = emission_material(f'Photo placeholder {label}', tuple(c * 0.5 for c in PALETTE[look]))
    elif kind == 'photo':
        shade = look * 0.45                      # keep placeholders dim, like dark photos
        mat, _ = emission_material(f'Photo placeholder {label}', (shade, shade, shade))
    else:
        mat = galaxy_material(f'Galaxy {label}', PALETTE[look], PALETTE[look + '_bright'], photo_file(label))
        ob['tint'] = look
    mesh.materials.append(mat)
    tiles_col.objects.link(ob)
    return ob


tiles = [make_tile(i, *row) for i, row in enumerate(TILES)]
bpy.context.view_layer.update()

# ---- Dust -------------------------------------------------------------------
points, colors, sizes, owners = [], [], [], []


def add_point(position, tint, owner=-1):
    mix = random.random() ** 2                     # mostly tint, some bright
    if DUST_COLOR:
        base, bright = hex_rgb(DUST_COLOR[0]), hex_rgb(DUST_COLOR[1])
    else:
        base, bright = PALETTE[tint], PALETTE[tint + '_bright']
    gain = random.uniform(0.35, 1.6)
    points.append(tuple(position))
    colors.append((*(gain * (b * (1 - mix) + br * mix) for b, br in zip(base, bright)), 1))
    sizes.append(DUST_RADIUS * random.uniform(0.45, 1.5))
    owners.append(owner)             # tile index the point belongs to, -1 = free


for tile_index, (ob, row) in enumerate(zip(tiles, TILES)):
    if row[1] != 'galaxy':
        continue
    w, h, tint = row[4], row[5], row[9]
    for _ in range(int(w * h * DUST_PER_AREA * DUST_AMOUNT)):
        # on the tile, with a soft spill past its edges and slightly in front
        u = random.gauss(0, 0.36) * w
        v = random.gauss(0, 0.36) * h
        lift = -abs(random.gauss(0, 0.12)) - 0.01
        add_point(ob.matrix_world @ Vector((u, lift, v)), tint, tile_index)

dust_mesh = bpy.data.meshes.new('Galaxy dust')
dust_mesh.from_pydata(points, [], [])
col_attr = dust_mesh.attributes.new('dust_color', 'FLOAT_COLOR', 'POINT')
col_attr.data.foreach_set('color', [c for rgba in colors for c in rgba])
size_attr = dust_mesh.attributes.new('dust_size', 'FLOAT', 'POINT')
size_attr.data.foreach_set('value', sizes)
dust = bpy.data.objects.new('Galaxy_dust', dust_mesh)
dust_col.objects.link(dust)

dust_mat, dust_em = emission_material('Galaxy dust glow', (1, 1, 1), 2.2)
attr = dust_mat.node_tree.nodes.new('ShaderNodeAttribute')
attr.attribute_name = 'dust_color'
dust_mat.node_tree.links.new(attr.outputs['Color'], dust_em.inputs['Color'])

# Geometry nodes: show each vertex as a small glowing point in renders.
group = bpy.data.node_groups.new('Dust points', 'GeometryNodeTree')
group.interface.new_socket(name='Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
group.interface.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
g_in = group.nodes.new('NodeGroupInput')
g_out = group.nodes.new('NodeGroupOutput')
to_points = group.nodes.new('GeometryNodeMeshToPoints')
radius = group.nodes.new('GeometryNodeInputNamedAttribute')
radius.data_type = 'FLOAT'
radius.inputs['Name'].default_value = 'dust_size'
set_mat = group.nodes.new('GeometryNodeSetMaterial')
set_mat.inputs['Material'].default_value = dust_mat
group.links.new(g_in.outputs[0], to_points.inputs['Mesh'])
group.links.new(radius.outputs['Attribute'], to_points.inputs['Radius'])
group.links.new(to_points.outputs['Points'], set_mat.inputs['Geometry'])
group.links.new(set_mat.outputs['Geometry'], g_out.inputs[0])
dust.modifiers.new('Dust points', 'NODES').node_group = group

# ---- Current --------------------------------------------------------------------
def catmull_rom(points, steps=24):
    """Smooth curve through the points (uniform Catmull-Rom)."""
    pts = [points[0] * 2 - points[1], *points, points[-1] * 2 - points[-2]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1:i + 3]
        for k in range(steps):
            t = k / steps
            out.append(0.5 * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (3 * p1 - p0 - 3 * p2 + p3) * t ** 3))
    out.append(points[-1].copy())
    return out


def resample(line, n):
    """n points evenly spaced along a polyline, and its length."""
    lengths = [0.0]
    for a, b in zip(line, line[1:]):
        lengths.append(lengths[-1] + (b - a).length)
    out, j = [], 0
    for i in range(n):
        s = lengths[-1] * i / (n - 1)
        while j < len(line) - 2 and lengths[j + 1] < s:
            j += 1
        seg = lengths[j + 1] - lengths[j]
        out.append(line[j].lerp(line[j + 1], (s - lengths[j]) / seg if seg else 0))
    return out, lengths[-1]


def path_frames(samples):
    """Normal and binormal along the path; the normal starts facing the camera
    plane and is carried along without twisting (parallel transport)."""
    n = len(samples)
    tangents = [(samples[min(i + 1, n - 1)] - samples[max(i - 1, 0)]).normalized() for i in range(n)]
    normal = tangents[0].cross((target - camera.location).normalized()).normalized()
    normals = []
    for t in tangents:
        normal = (normal - t * normal.dot(t)).normalized()
        normals.append(normal)
    return normals, [t.cross(nm) for t, nm in zip(tangents, normals)]


def smoothstep(a, b, x):
    x = min(max((x - a) / (b - a), 0.0), 1.0)
    return x * x * (3 - 2 * x)


flow_paths, flow_data = [], []         # flow_data rows match flow.bin
still_points, still_colors, still_sizes = [], [], []
base, bright = hex_rgb(FLOW_COLOR[0]), hex_rgb(FLOW_COLOR[1])
for curve, (path, count, width, fibres, speed) in enumerate(FLOWS):
    samples, length = resample(catmull_rom([screen_point(*spread(x, y), d / TILE_SCALE) for x, y, d in path]),
                               FLOW_SAMPLES)
    normals, binormals = path_frames(samples)
    flow_paths.append({'length': round(length, 4), 'speed': speed, 'points': [y_up(p) for p in samples],
                       'normals': [y_up(v) for v in normals], 'binormals': [y_up(v) for v in binormals]})
    strands = [(abs(random.gauss(0, 0.5)) * width, random.uniform(0, math.tau)) for _ in range(fibres)]
    for _ in range(int(count * FLOW_AMOUNT)):
        if random.random() < 0.8:      # on a fibre
            (r, theta), jitter = random.choice(strands), 0.012
        else:                          # loose haze around the current
            r, theta, jitter = abs(random.gauss(0, 0.6)) * width, random.uniform(0, math.tau), 0.05
        t0, ja, jb = random.random(), random.gauss(0, jitter), random.gauss(0, jitter)
        mix, gain = random.random() ** 2, random.uniform(0.6, 2.0)
        color = [gain * (b * (1 - mix) + br * mix) for b, br in zip(base, bright)]
        size = DUST_RADIUS * random.uniform(0.4, 1.25)
        flow_data.append((curve, t0, r, theta, ja, jb, size, *color, random.random()))
        # The still shows the current at time 0, placed the way hero.js places it.
        f = t0 * (FLOW_SAMPLES - 1)
        i = min(int(f), FLOW_SAMPLES - 2)
        u = f - i
        nm = normals[i].lerp(normals[i + 1], u).normalized()
        bn = binormals[i].lerp(binormals[i + 1], u).normalized()
        angle, taper = theta + FLOW_TWIST * t0, 0.35 + 0.65 * math.sin(math.pi * t0)
        still_points.append(samples[i].lerp(samples[i + 1], u)
                            + (nm * math.cos(angle) + bn * math.sin(angle)) * r * taper + nm * ja + bn * jb)
        fade = smoothstep(0, 0.06, t0) * (1 - smoothstep(0.9, 1, t0))
        still_colors.append((*(c * fade for c in color), 1))
        still_sizes.append(size)

current_mesh = bpy.data.meshes.new('Galaxy current')
current_mesh.from_pydata(still_points, [], [])
current_mesh.attributes.new('dust_color', 'FLOAT_COLOR', 'POINT').data.foreach_set(
    'color', [c for rgba in still_colors for c in rgba])
current_mesh.attributes.new('dust_size', 'FLOAT', 'POINT').data.foreach_set('value', still_sizes)
current = bpy.data.objects.new('Galaxy_current', current_mesh)
dust_col.objects.link(current)
current.modifiers.new('Dust points', 'NODES').node_group = group

# ---- World, camera, render ----------------------------------------------------
world = bpy.data.worlds.new('Studio black')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs[0].default_value = (*PALETTE['background'], 1)
scene.world = world


scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 24
scene.cycles.use_denoising = False
scene.cycles.max_bounces = 1
scene.view_settings.view_transform = 'Standard'
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'JPEG'
scene.render.image_settings.quality = 85
scene.render.filepath = str(OUT / 'poster.jpg')

bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'stop.blend'))
bpy.ops.render.render(write_still=True)

# ---- Browser export -----------------------------------------------------------
bpy.ops.object.select_all(action='DESELECT')
for ob in tiles:
    ob.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(OUT / 'stop.glb'), export_format='GLB', use_selection=True,
                          export_extras=True, export_materials='NONE', export_animations=False)

with open(OUT / 'dust.bin', 'wb') as f:
    for p, c, size, owner in zip(points, colors, sizes, owners):
        f.write(struct.pack('<8f', *y_up(p), c[0], c[1], c[2], size, owner))

with open(OUT / 'flow.bin', 'wb') as f:
    for row in flow_data:
        f.write(struct.pack('<11f', *row))

aspect = scene.render.resolution_x / scene.render.resolution_y
Y_UP = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0)))      # Blender Z-up -> three.js Y-up
rest_q = (Y_UP @ camera.matrix_world.to_3x3()).to_quaternion()
contract = {
    'id': '01-hero',
    'blender': bpy.app.version_string,
    # The camera at rest, in this stop's own frame (three.js axes). The route
    # places the stop in the world so that the route camera lands exactly here.
    'rest': {'position': y_up(camera.location), 'quaternion': [round(v, 6) for v in (rest_q.x, rest_q.y, rest_q.z, rest_q.w)],
             'horizontal_fov_deg': round(math.degrees(2 * math.atan(cam_data.sensor_width / 2 / cam_data.lens)), 3),
             'design_aspect': round(aspect, 4)},
    'brief': BRIEF,
    'palette_linear': {k: [round(c, 5) for c in v] for k, v in PALETTE.items()},
    'tiles': [{'name': ob.name, 'label': row[0], 'kind': row[1], 'width': row[4], 'height': row[5],
               'look': row[9]} for ob, row in zip(tiles, TILES)],
    'dust': {'file': 'dust.bin', 'count': len(points), 'floats_per_point': 8,
             'layout': ['x', 'y', 'z', 'r', 'g', 'b', 'size', 'owner_tile_index_or_-1']},
    'flow': {'file': 'flow.bin', 'count': len(flow_data), 'floats_per_point': 11,
             'layout': ['path', 't', 'radius', 'angle', 'jitter_n', 'jitter_b', 'size', 'r', 'g', 'b', 'seed'],
             'samples': FLOW_SAMPLES, 'twist': FLOW_TWIST, 'paths': flow_paths},
}
(OUT / 'stop.json').write_text(json.dumps(contract, indent=2))
print(f'HERO_DONE tiles={len(tiles)} dust_points={len(points)} flow_points={len(flow_data)}')
