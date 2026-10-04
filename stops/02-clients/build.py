"""Stop 02, clients ("Creative for" logo grid) - detail pass (Blender 4.5 LTS, CPU render).

The 5 x 2 grid of cells floating at slightly different depths (approved graybox),
wordmarks set in each brand's typeface like the landing HTML (fonts/), and the
stop's current threading the grid lines (the only particles at this stop). Cells, hairlines and
wordmarks are each merged into one mesh with a per-vertex cell number (_CELL), so
the browser draws the grid in three calls and lifts and lights one cell at a time.
Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python stops/02-clients/build.py
Outputs beside this file:
  poster.jpg, stop.blend     preview render (also the fallback poster) and editable scene
  stop.glb                   Cells, Lines, Words: three merged meshes with UVs and a _CELL attribute
  flow.bin                   current particles (float32 x 11, see tools/flow_common.py)
  stop.json                  contract: rest camera, how the route enters, brief, cells, flow
"""
import bpy, json, math, random, struct, sys
from pathlib import Path
from mathutils import Vector, Matrix
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from flow_common import make_current

OUT = Path(__file__).resolve().parent
SEED = 23

# What was agreed for this stop (the five content questions), kept in stop.json.
BRIEF = {
    'status': 'answers recorded 2026-10-04; graybox awaiting approval',
    'text': "3D wordmarks in the cells. HTML curtain: the small 'CREATIVE FOR' label only. "
            'The ten brand names are also real text in the section: read by screen readers, visible in the flat fallback.',
    'buttons': 'none',
    'button_behaviour': 'n/a',
    'scene_behaviour': 'Cells float at slightly different depths. Idle: nothing moves. '
                       'Hover (like catalyst-growth.com logo grid): hovered cell lifts toward the camera, its wordmark goes '
                       'full white while the others dim to 50%, a thin violet-blue-teal gradient border rotates around it, '
                       'a violet glow fades in from its top-left corner. The current parts around the cursor. '
                       'Monochrome apart from the hover. Arrives frozen and black and white; live once the section is on screen.',
    'current': 'Enters where the journey current from stop 01 ends, threads the grid lines, leaves on the left '
               '(the next transition tilts left).',
    'media': 'the ten wordmarks only',
    'particles': 'only the current; no dust (changed 2026-10-04)',
    'wordmarks': 'Typed in Google fonts like the landing HTML; new: Perplexity (Inter Tight 500, lowercase), '
                 'Granola (Fraunces 500), Canva (Pacifico).',
}

# How the camera reaches this stop from stop 01 (tools/build_route.py): a half circle
# of `radius` swinging toward stop 01's objects while tilting `tilt_degrees` `tilt`,
# then a straight `travel` along the new view.
ENTER = {'tilt': 'down', 'tilt_degrees': 60, 'radius': 8.0, 'travel': 8.0}

CAMERA_AT = (0.0, -11.0, 0.0)
CAMERA_LENS = 28
FRAME = (1616, 875)

# ---- Grid (from the landing HTML: 5 x 2 cells of 328 x 137 px, hairlines at 8% white) ----
# Slots left to right, top row first. The landing page's seven plus the three new ones
# in the empty slots (Perplexity, Granola top left; Canva bottom right).
BRANDS = [
    ['perplexity', 'Granola', 'Lovable', 'fyxer', 'MAGIC AI'],
    ['Mozart', 'cleo', 'VIKTOR', 'Jack & Jill', 'Canva'],
]
GRID_WIDTH = 0.80            # share of the frame width the grid covers at rest
GRID_CENTRE = (0.5, 0.52)    # where the grid's centre lands in the frame (0..1 from top-left)
CELL_RATIO = 137 / 328       # cell height / width
REST_DEPTH = 11.0            # distance of the grid from the rest camera
DEPTH_OFFSETS = [            # each cell floats this much further (+) or nearer (-) than REST_DEPTH
    [0.0, 0.6, -0.4, 0.3, -0.6],
    [0.5, -0.3, 0.7, -0.5, 0.2],
]
HAIRLINE = 0.012             # outline width at REST_DEPTH, scene units
# Wordmarks, from the landing HTML (font, px size in a 137 px tall cell, letter spacing px, case).
# The three new brands use the fonts agreed in the brief. The fonts/ files are Google Fonts
# static instances with overlapping outlines removed (fontTools), so Blender fills them cleanly.
WORDMARKS = {
    'Lovable':     ('Outfit-600.ttf', 34, -1.02, None),
    'fyxer':       ('SpaceGrotesk-500.ttf', 36, -1.44, 'lower'),
    'MAGIC AI':    ('Syne-700.ttf', 26, 1.04, 'upper'),
    'Mozart':      ('DMSerifDisplay-400.ttf', 38, -0.38, None),
    'cleo':        ('Nunito-800.ttf', 38, -1.14, 'lower'),
    'VIKTOR':      ('Archivo-700.ttf', 28, 3.36, 'upper'),
    'Jack & Jill': ('InstrumentSerif-Italic.ttf', 38, -0.38, None),
    'perplexity':  ('InterTight-500.ttf', 34, -0.68, 'lower'),
    'Granola':     ('Fraunces-500.ttf', 36, -0.72, None),
    'Canva':       ('Pacifico-400.ttf', 40, 0.0, None),       # Pacifico's letters run small for their size
}
CELL_PX = 137                # cell height in the landing HTML, for the px sizes above
EM_ADVANCE = 0.55            # average glyph advance in em, to turn letter spacing into Blender's spacing scale

# ---- Current: control points (x, y in the frame, depth). Enters where the journey
# current from stop 01 ends (lower right, near), runs along the line between the two
# rows weaving in front of and behind the cells, and leaves off the left edge. ----
CURRENT_PATH = [
    (0.68, 0.79, 7.0),     # where the journey current ends
    (0.80, 0.68, 9.0),
    (0.92, 0.52, 11.9),    # behind the grid at its right end, on the middle line
    (0.72, 0.52, 10.1),    # in front
    (0.52, 0.52, 11.9),    # behind
    (0.32, 0.52, 10.1),    # in front
    (0.13, 0.52, 11.7),    # behind
    (-0.06, 0.50, 9.6),    # out past the left edge
    (-0.30, 0.47, 8.0),    # the next journey (tilting left) picks it up here
]
FLOW = {'particles': 7000, 'width': 0.196, 'fibres': 34, 'speed': 0.48, 'twist': 9.0, 'samples': 200,
        'color': ('#a4a4aa', '#e2e2e6')}
PARTICLE_RADIUS = 0.0055     # current particle size, as at stop 01

CELL_COLOR = (0.00061, 0.00061, 0.00121)   # the page's black, like the live site's cells (linear)
LINE_COLOR = (0.00719, 0.00719, 0.00719)   # white at 8% over black, the live site's hairlines (linear)
WORD_COLOR = (0.48, 0.48, 0.48)     # white at 72%, like the landing HTML (linear)


def hex_rgb(h):
    h = h.lstrip('#')
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb)


def y_up(v):
    return [round(v[0], 5), round(v[2], 5), round(-v[1], 5)]


# ---- Scene and camera ----------------------------------------------------------
random.seed(SEED)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.resolution_x, scene.render.resolution_y = FRAME
cam_data = bpy.data.cameras.new('Stop camera')
cam_data.lens = CAMERA_LENS
camera = bpy.data.objects.new('Stop camera', cam_data)
scene.collection.objects.link(camera)
camera.location = CAMERA_AT
target = Vector((0, 0, 0))
camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = camera
bpy.context.view_layer.update()
_frame = [Vector(c) / -c[2] for c in cam_data.view_frame(scene=scene)]   # frame corners at depth 1
FRAME_LEFT, FRAME_RIGHT = min(c.x for c in _frame), max(c.x for c in _frame)
FRAME_TOP, FRAME_BOTTOM = max(c.y for c in _frame), min(c.y for c in _frame)
FRAME_W, FRAME_H = FRAME_RIGHT - FRAME_LEFT, FRAME_TOP - FRAME_BOTTOM      # frame size at depth 1


def screen_point(x, y, depth):
    """World point that lands at (x, y) in the frame (0..1 from top-left), depth units ahead."""
    local = Vector((FRAME_LEFT + x * FRAME_W, FRAME_TOP - y * FRAME_H, -1)) * depth
    return camera.matrix_world @ local


def emission(name, color, strength=1.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    em, out = nodes.new('ShaderNodeEmission'), nodes.new('ShaderNodeOutputMaterial')
    em.inputs['Color'].default_value = (*color, 1)
    em.inputs['Strength'].default_value = strength
    mat.node_tree.links.new(em.outputs['Emission'], out.inputs['Surface'])
    return mat


def plane(name, width, height, location, material):
    hw, hh = width / 2, height / 2
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([(-hw, 0, -hh), (hw, 0, -hh), (hw, 0, hh), (-hw, 0, hh)], [], [(0, 1, 2, 3)])
    uv = mesh.uv_layers.new(name='UVMap')
    for loop, co in zip(uv.data, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        loop.uv = co
    mesh.materials.append(material)
    ob = bpy.data.objects.new(name, mesh)
    ob.location = location
    scene.collection.objects.link(ob)
    return ob


cell_mat, line_mat, word_mat = emission('Cell', CELL_COLOR), emission('Hairline', LINE_COLOR), emission('Wordmark', WORD_COLOR)

# ---- Cells: each covers its grid slot from the rest view, at its own depth -----
cell_w = GRID_WIDTH / 5                                   # share of the frame width
cell_h = cell_w * CELL_RATIO * FRAME[0] / FRAME[1]        # share of the frame height
left = GRID_CENTRE[0] - GRID_WIDTH / 2
top = GRID_CENTRE[1] - cell_h
objects, cells = [], []
for row, names in enumerate(BRANDS):
    for col, brand in enumerate(names):
        depth = REST_DEPTH + DEPTH_OFFSETS[row][col]
        centre = screen_point(left + (col + 0.5) * cell_w, top + (row + 0.5) * cell_h, depth)
        w, h = cell_w * FRAME_W * depth, cell_h * FRAME_H * depth
        name = f'Cell_{row}{col}'
        objects.append(plane(name, w, h, centre, cell_mat))
        t = HAIRLINE * depth / REST_DEPTH                  # hairline frame, just in front of the cell
        for side, (ow, oh, dx, dz) in {'T': (w, t, 0, (h - t) / 2), 'B': (w, t, 0, -(h - t) / 2),
                                       'L': (t, h, -(w - t) / 2, 0), 'R': (t, h, (w - t) / 2, 0)}.items():
            objects.append(plane(f'Line_{row}{col}{side}', ow, oh, centre + Vector((dx, -0.004, dz)), line_mat))
        font, px, spacing, case = WORDMARKS[brand]
        bpy.ops.object.text_add(location=centre + Vector((0, -0.01, 0)), rotation=(math.radians(90), 0, 0))
        word = bpy.context.active_object
        word.data.body = brand.lower() if case == 'lower' else brand.upper() if case == 'upper' else brand
        word.data.font = bpy.data.fonts.load(str(OUT / 'fonts' / font), check_existing=True)
        word.data.size = px / CELL_PX * h
        word.data.space_character = 1 + spacing / px / EM_ADVANCE
        word.data.align_x, word.data.align_y = 'CENTER', 'CENTER'
        word.data.materials.append(word_mat)
        bpy.ops.object.convert(target='MESH')
        word.name = f'Word_{row}{col}'
        objects.append(word)
        cells.append({'name': name, 'word': word.name, 'brand': brand, 'row': row, 'col': col, 'centre': y_up(centre),
                      'depth': round(depth, 3), 'width': round(w, 4), 'height': round(h, 4)})

# ---- Current ----------------------------------------------------------------------
flow_paths_v, flow_rows, still = make_current(
    [([screen_point(x, y, d) for x, y, d in CURRENT_PATH], FLOW['particles'], FLOW['width'], FLOW['fibres'], FLOW['speed'])],
    facing=target - camera.location, samples=FLOW['samples'], amount=1.0, twist=FLOW['twist'],
    base=hex_rgb(FLOW['color'][0]), bright=hex_rgb(FLOW['color'][1]), radius=PARTICLE_RADIUS)

# Points for the preview render: the current as small glowing spheres.
point_mat = emission('Point glow', (1, 1, 1), 2.2)
attr = point_mat.node_tree.nodes.new('ShaderNodeAttribute')
attr.attribute_name = 'dust_color'
point_mat.node_tree.links.new(attr.outputs['Color'], point_mat.node_tree.nodes['Emission'].inputs['Color'])
group = bpy.data.node_groups.new('Dust points', 'GeometryNodeTree')
group.interface.new_socket(name='Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
group.interface.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
g_in, g_out = group.nodes.new('NodeGroupInput'), group.nodes.new('NodeGroupOutput')
to_points, radius = group.nodes.new('GeometryNodeMeshToPoints'), group.nodes.new('GeometryNodeInputNamedAttribute')
radius.data_type = 'FLOAT'
radius.inputs['Name'].default_value = 'dust_size'
set_mat = group.nodes.new('GeometryNodeSetMaterial')
set_mat.inputs['Material'].default_value = point_mat
group.links.new(g_in.outputs[0], to_points.inputs['Mesh'])
group.links.new(radius.outputs['Attribute'], to_points.inputs['Radius'])
group.links.new(to_points.outputs['Points'], set_mat.inputs['Geometry'])
group.links.new(set_mat.outputs['Geometry'], g_out.inputs[0])
for label, pts, cols, sizes in (('Current', [p for p, _, _ in still], [c for _, c, _ in still], [z for _, _, z in still]),):
    mesh = bpy.data.meshes.new(label)
    mesh.from_pydata(pts, [], [])
    mesh.attributes.new('dust_color', 'FLOAT_COLOR', 'POINT').data.foreach_set('color', [c for rgba in cols for c in rgba])
    mesh.attributes.new('dust_size', 'FLOAT', 'POINT').data.foreach_set('value', sizes)
    ob = bpy.data.objects.new(label, mesh)
    scene.collection.objects.link(ob)
    ob.modifiers.new('Dust points', 'NODES').node_group = group

# ---- Render -----------------------------------------------------------------------
world = bpy.data.worlds.new('Black')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs[0].default_value = (0.00061, 0.00061, 0.00121, 1)
scene.world = world
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 24
scene.cycles.use_denoising = False
scene.cycles.max_bounces = 1
scene.view_settings.view_transform = 'Standard'
scene.render.image_settings.file_format = 'JPEG'
scene.render.image_settings.quality = 85
scene.render.filepath = str(OUT / 'poster.jpg')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'stop.blend'))
bpy.ops.render.render(write_still=True)

# ---- Browser export: three merged meshes, each vertex tagged with its cell ---------
def merge(prefix):
    parts = [ob for ob in scene.objects if ob.type == 'MESH' and ob.name.startswith(prefix + '_')]
    for ob in parts:
        index = 5 * int(ob.name[len(prefix) + 1]) + int(ob.name[len(prefix) + 2])     # row * 5 + col
        attr = ob.data.attributes.new('_CELL', 'FLOAT', 'POINT')
        attr.data.foreach_set('value', [float(index)] * len(ob.data.vertices))
    bpy.ops.object.select_all(action='DESELECT')
    for ob in parts:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    merged = bpy.context.active_object
    merged.name = {'Cell': 'Cells', 'Line': 'Lines', 'Word': 'Words'}[prefix]
    return merged


merged = [merge(prefix) for prefix in ('Cell', 'Line', 'Word')]
bpy.ops.object.select_all(action='DESELECT')
for ob in merged:
    ob.select_set(True)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)   # vertices in the stop's own frame
bpy.ops.export_scene.gltf(filepath=str(OUT / 'stop.glb'), export_format='GLB', use_selection=True,
                          export_materials='NONE', export_animations=False, export_attributes=True)
with open(OUT / 'flow.bin', 'wb') as f:
    for row in flow_rows:
        f.write(struct.pack('<11f', *row))

Y_UP = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0)))
q = (Y_UP @ camera.matrix_world.to_3x3()).to_quaternion()
(OUT / 'stop.json').write_text(json.dumps({
    'id': '02-clients',
    'blender': bpy.app.version_string,
    'rest': {'position': y_up(camera.location), 'quaternion': [round(v, 6) for v in (q.x, q.y, q.z, q.w)],
             'horizontal_fov_deg': round(math.degrees(2 * math.atan(cam_data.sensor_width / 2 / cam_data.lens)), 3),
             'design_aspect': round(FRAME[0] / FRAME[1], 4)},
    'enter': ENTER,
    'brief': BRIEF,
    'colors': {'cell': CELL_COLOR, 'line': LINE_COLOR, 'word': WORD_COLOR},
    'cells': cells,
    'flow': {'file': 'flow.bin', 'count': len(flow_rows), 'floats_per_point': 11,
             'layout': ['path', 't', 'radius', 'angle', 'jitter_n', 'jitter_b', 'size', 'r', 'g', 'b', 'seed'],
             'samples': FLOW['samples'], 'twist': FLOW['twist'],
             'paths': [{'length': round(p['length'], 4), 'speed': p['speed'], 'points': [y_up(v) for v in p['points']],
                        'normals': [y_up(v) for v in p['normals']], 'binormals': [y_up(v) for v in p['binormals']]}
                       for p in flow_paths_v]},
}, indent=1))
print(f'STOP_DONE 02-clients cells={len(cells)} flow={len(flow_rows)}')
