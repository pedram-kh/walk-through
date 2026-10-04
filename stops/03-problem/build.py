"""Stop 03, the problem ("AI moves fast") (Blender 4.5 LTS, CPU render).

Three rows of 5 cards on screen (the landing HTML's drifting rows; 6 per row in the
drift loop), upright and turned on their vertical axes in a checkerboard zigzag
(toward / away from the screen), laid out so the whole section fits one viewport with the HTML text around it, and the stop's current: it enters from the
right, splits into two strands that go around the card block (one above, one
below and up the left side) and both leave through the top of the screen.
Card faces (photo, hairline border, label chip) come from cards.jpg, made by atlas.py.
Run (after atlas.py):
  /Applications/Blender.app/Contents/MacOS/Blender --background --python stops/03-problem/build.py
Outputs beside this file:
  poster.jpg, stop.blend     preview render (also the fallback poster) and editable scene
  stop.glb                   the cards at rest (the route's clearance check; the browser builds them from stop.json)
  flow.bin                   current particles (float32 x 11, see tools/flow_common.py)
  stop.json                  contract: rest camera, how the route enters, brief, rows, cards, flow
"""
import bpy, json, math, random, struct, sys
from pathlib import Path
from mathutils import Vector, Matrix, Euler
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from flow_common import make_current

OUT = Path(__file__).resolve().parent
SEED = 31

# What was agreed for this stop (the five content questions), kept in stop.json.
BRIEF = {
    'status': 'approved 2026-10-04',
    'text': "All HTML (no section label, removed at your request): 'AI moves fast. / Your creative needs to keep up.', the three "
            "row labels (01 New features., 02 New use cases., 03 New competitors.) with direction arrows, "
            "the paragraph and 'More creative = More learnings = More opportunities to scale.' "
            'The whole section fits one viewport.',
    'buttons': 'none (the row arrows only show direction)',
    'button_behaviour': 'n/a',
    'scene_behaviour': 'Three rows of cards drift sideways forever like the landing HTML (rows 1 and 3 right '
                       'at 30 px/s, row 2 left at 34 px/s, faded at the row ends). Cards stand upright, '
                       'turned 25 degrees on their vertical axes, toward / away from the screen in a checkerboard. Cards near the cursor tilt and lift like the hero tiles; the current parts around the '
                       'cursor (same at every stop). Arrives frozen and black and white; colour and motion once live.',
    'current': 'Enters from the right, splits into two strands that go around the card block (one above, one '
               'below and up the left side) and both leave through the top of the screen.',
    'media': 'Photos from catalyst-growth.com (the set downloaded for stop 01) on the cards, with the landing '
             "HTML's hairline border and label chip (the landing's coloured placeholder sits under the photo, so it never shows).",
    'transition_in': 'tilt left, same move as before (half circle radius 8, 60 degrees, travel 8)',
}
ENTER = {'tilt': 'left', 'tilt_degrees': 60, 'radius': 8.0, 'travel': 8.0}

CAMERA_AT = (0.0, -11.0, 0.0)
CAMERA_LENS = 28
FRAME = (1616, 875)

# ---- Rows of cards (landing HTML: 248 x 183 px cards, 20 px apart, drifting rows) -----------
CARD_RATIO = 248 / 183        # width / height
GAP = 20 / 248                # gap between cards, as a share of the card width
ROW_Y = [0.40, 0.575, 0.75]   # row centres in the frame (0..1 from the top)
ROW_LEFT = 0.35               # where the rows start: a clear gap after the HTML row labels
ROW_RIGHT = 0.93              # ...and end, short of the HTML drift arrows
CARDS_PER_ROW = 5             # on screen at rest
LOOP = 6                      # cards per row in the drift loop: one waits off the row's end (even, so the
                              # checkerboard holds when a card wraps round); the drift fades cards at the row ends
# Drift in cards per second (landing: 30 / 34 px/s with 248 + 20 px per card); + = to the right
ROW_SPEED = [30 / 268, -34 / 268, 30 / 268]
ZIGZAG_DEG = 25               # cards upright, turned on their vertical axis: + and - in a checkerboard
REST_DEPTH = 11.0

# ---- Current: one start, two strands around the card block, both out through the top ----
START = [(1.10, 0.62, 9.0), (1.00, 0.56, 10.4)]
STRAND_TOP = START + [
    (1.03, 0.40, 11.4),       # up past the right end of the rows, just off screen (clear of the arrows)
    (0.95, 0.22, 10.4),
    (0.86, -0.12, 8.0),       # out through the top, right of the title
]
STRAND_BOTTOM = START + [
    (1.03, 0.76, 10.6),       # down past the right end, off screen
    (0.92, 0.852, 11.6),      # along the bottom of row 3, under the cards and above the copy
    (0.66, 0.852, 11.0),
    (0.42, 0.852, 11.6),
    (0.322, 0.83, 10.8),      # round the bottom-left corner
    (0.31, 0.575, 11.4),      # up the left side, in the gap between the row labels and the cards
    (0.33, 0.30, 10.8),       # round the top-left corner
    (0.55, 0.292, 11.4),      # along the top of row 1, under the title
    (0.74, 0.292, 10.8),
    (0.80, 0.16, 9.6),
    (0.78, -0.12, 8.0),       # out through the top, right of the title
]
FLOW = {'particles': 5200, 'width': 0.196, 'fibres': 34, 'speed': 0.48, 'twist': 9.0, 'samples': 200,
        'color': ('#a4a4aa', '#e2e2e6')}
PARTICLE_RADIUS = 0.0055

ATLAS = json.loads((OUT / 'cards.json').read_text())   # card faces, from atlas.py


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


def plane(name, width, height, material):
    hw, hh = width / 2, height / 2
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([(-hw, 0, -hh), (hw, 0, -hh), (hw, 0, hh), (-hw, 0, hh)], [], [(0, 1, 2, 3)])
    uv = mesh.uv_layers.new(name='UVMap')
    for loop, co in zip(uv.data, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        loop.uv = co
    mesh.materials.append(material)
    ob = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(ob)
    return ob


card_mat = emission('Card face', (1, 1, 1))
_tex = card_mat.node_tree.nodes.new('ShaderNodeTexImage')
_tex.image = bpy.data.images.load(str(OUT / ATLAS['file']))
_tex.interpolation = 'Cubic'
card_mat.node_tree.links.new(_tex.outputs['Color'], card_mat.node_tree.nodes['Emission'].inputs['Color'])

# ---- Cards ------------------------------------------------------------------------
row_span = (ROW_RIGHT - ROW_LEFT) * FRAME_W * REST_DEPTH
card_w_world = row_span / (CARDS_PER_ROW + (CARDS_PER_ROW - 1) * GAP)   # 5 cards and their gaps fill the row
card_h_world = card_w_world / CARD_RATIO
pitch_world = card_w_world * (1 + GAP)                      # one card plus its gap
objects, cards = [], []
for row, y in enumerate(ROW_Y):
    row_centre = screen_point(0.5, y, REST_DEPTH)
    left = screen_point(ROW_LEFT, y, REST_DEPTH).x
    for i in range(LOOP):
        turn = ZIGZAG_DEG if (i + row) % 2 == 0 else -ZIGZAG_DEG
        x = left + card_w_world / 2 + i * pitch_world
        centre = Vector((x, row_centre.y, row_centre.z))
        cell = ATLAS['cells'][row * LOOP + i]
        name = f'Card_{row}{i}'
        card = plane(name, card_w_world, card_h_world, card_mat)
        u0, v0, du, dv = cell['uv']
        for loop, (a, b) in zip(card.data.uv_layers[0].data, [(0, 0), (1, 0), (1, 1), (0, 1)]):
            loop.uv = (u0 + a * du, v0 + b * dv)
        card.location = centre
        card.rotation_euler = Euler((0, 0, math.radians(turn)), 'XYZ')
        card.hide_render = i >= CARDS_PER_ROW               # waits off the row's end
        objects.append(card)
        cards.append({'name': name, 'row': row, 'index': i, 'label': cell['label'], 'photo': cell['photo'],
                      'uv': cell['uv'], 'centre': y_up(centre), 'turn_deg': turn})
# Rows for the browser (three.js axes): card k sits at left + width / 2 + (k + drift) * pitch,
# wrapped into [-1, LOOP - 1) pitches so the wrap happens off the row's ends.
rows = [{'row': r, 'y': ROW_Y[r], 'centre': y_up(screen_point(0.5, ROW_Y[r], REST_DEPTH)),
         'speed_cards_per_s': round(ROW_SPEED[r], 4),
         'left': round(screen_point(ROW_LEFT, ROW_Y[r], REST_DEPTH).x, 4),
         'right': round(screen_point(ROW_RIGHT, ROW_Y[r], REST_DEPTH).x, 4),
         'pitch': round(pitch_world, 4), 'on_screen': CARDS_PER_ROW, 'loop': LOOP} for r in range(len(ROW_Y))]

# ---- Current ----------------------------------------------------------------------
flow_paths_v, flow_rows, still = make_current(
    [([screen_point(x, y, d) for x, y, d in path], FLOW['particles'], FLOW['width'], FLOW['fibres'], FLOW['speed'])
     for path in (STRAND_TOP, STRAND_BOTTOM)],
    facing=target - camera.location, samples=FLOW['samples'], amount=1.0, twist=FLOW['twist'],
    base=hex_rgb(FLOW['color'][0]), bright=hex_rgb(FLOW['color'][1]), radius=PARTICLE_RADIUS)

# Points for the preview render: the current as small glowing spheres.
point_mat = emission('Point glow', (1, 1, 1), 2.2)
attr = point_mat.node_tree.nodes.new('ShaderNodeAttribute')
attr.attribute_name = 'point_color'
point_mat.node_tree.links.new(attr.outputs['Color'], point_mat.node_tree.nodes['Emission'].inputs['Color'])
group = bpy.data.node_groups.new('Points', 'GeometryNodeTree')
group.interface.new_socket(name='Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
group.interface.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
g_in, g_out = group.nodes.new('NodeGroupInput'), group.nodes.new('NodeGroupOutput')
to_points, radius = group.nodes.new('GeometryNodeMeshToPoints'), group.nodes.new('GeometryNodeInputNamedAttribute')
radius.data_type = 'FLOAT'
radius.inputs['Name'].default_value = 'point_size'
set_mat = group.nodes.new('GeometryNodeSetMaterial')
set_mat.inputs['Material'].default_value = point_mat
group.links.new(g_in.outputs[0], to_points.inputs['Mesh'])
group.links.new(radius.outputs['Attribute'], to_points.inputs['Radius'])
group.links.new(to_points.outputs['Points'], set_mat.inputs['Geometry'])
group.links.new(set_mat.outputs['Geometry'], g_out.inputs[0])
mesh = bpy.data.meshes.new('Current')
mesh.from_pydata([p for p, _, _ in still], [], [])
mesh.attributes.new('point_color', 'FLOAT_COLOR', 'POINT').data.foreach_set('color', [c for _, rgba, _ in still for c in rgba])
mesh.attributes.new('point_size', 'FLOAT', 'POINT').data.foreach_set('value', [z for _, _, z in still])
current = bpy.data.objects.new('Current', mesh)
scene.collection.objects.link(current)
current.modifiers.new('Points', 'NODES').node_group = group

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

# ---- Browser export ---------------------------------------------------------------
bpy.ops.object.select_all(action='DESELECT')
for ob in objects:
    ob.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(OUT / 'stop.glb'), export_format='GLB', use_selection=True,
                          export_materials='NONE', export_animations=False)
with open(OUT / 'flow.bin', 'wb') as f:
    for row in flow_rows:
        f.write(struct.pack('<11f', *row))

Y_UP = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0)))
q = (Y_UP @ camera.matrix_world.to_3x3()).to_quaternion()
(OUT / 'stop.json').write_text(json.dumps({
    'id': '03-problem',
    'blender': bpy.app.version_string,
    'rest': {'position': y_up(camera.location), 'quaternion': [round(v, 6) for v in (q.x, q.y, q.z, q.w)],
             'horizontal_fov_deg': round(math.degrees(2 * math.atan(cam_data.sensor_width / 2 / cam_data.lens)), 3),
             'design_aspect': round(FRAME[0] / FRAME[1], 4)},
    'enter': ENTER,
    'brief': BRIEF,
    'card': {'width': round(card_w_world, 4), 'height': round(card_h_world, 4), 'zigzag_deg': ZIGZAG_DEG,
             'atlas': ATLAS['file'], 'atlas_size': ATLAS['size']},
    'rows': rows,
    'cards': cards,
    'flow': {'file': 'flow.bin', 'count': len(flow_rows), 'floats_per_point': 11,
             'layout': ['path', 't', 'radius', 'angle', 'jitter_n', 'jitter_b', 'size', 'r', 'g', 'b', 'seed'],
             'samples': FLOW['samples'], 'twist': FLOW['twist'],
             'paths': [{'length': round(p['length'], 4), 'speed': p['speed'], 'points': [y_up(v) for v in p['points']],
                        'normals': [y_up(v) for v in p['normals']], 'binormals': [y_up(v) for v in p['binormals']]}
                       for p in flow_paths_v]},
}, indent=1))
print(f'STOP_DONE 03-problem cards={len(cards)} flow={len(flow_rows)}')
