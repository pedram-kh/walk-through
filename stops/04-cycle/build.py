"""Stop 04, the creative cycle (landing section 13) - graybox pass (Blender 4.5 LTS, CPU render).

Graybox: the cycle ring on the left of the frame (a thin ring with a faint disc), the four
stage spheres (Strategy top, Testing right, Iteration bottom, Scale left), the signal
sphere and its trail arc, and the Catalyst mark in the centre (extruded from core.svg,
the landing's CycleCore outline) with its glowing core square. All text is HTML (title,
the four rows on the right, the four stage labels). The stop's current arrives from
below, goes around the outside of the ring and leaves through the left of the screen.
Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python stops/04-cycle/build.py
Outputs beside this file:
  poster.jpg, stop.blend     preview render (also the fallback poster) and editable scene
  stop.glb                   ring, disc, stage spheres, signal, trail, mark and core
  flow.bin                   current particles (float32 x 11, see tools/flow_common.py)
  stop.json                  contract: rest camera, how the route enters, brief, ring, flow
"""
import bpy, json, math, random, struct, sys
from pathlib import Path
from mathutils import Vector, Matrix, Euler
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from flow_common import make_current

OUT = Path(__file__).resolve().parent
SEED = 41

# What was agreed for this stop (the five content questions), kept in stop.json.
BRIEF = {
    'status': 'graybox approved 2026-10-04; detail pass in progress',
    'route': "Landing section 13 'Creative cycle' is stop 04; landing sections 03-12 are skipped for now "
             '(may be added later).',
    'text': "All HTML except the mark: the title 'Creative cycle', the four rows (01 Strategy. 02 Testing. "
            "03 Iteration. 04 Scale.) and the four stage labels on the ring. No section label (no "
            "'13 — Creative cycle'). The whole section fits one viewport: ring on the left, list on the right.",
    'buttons': 'The four list rows (HTML). The stage spheres on the ring are not buttons.',
    'button_behaviour': "As the landing page: the active row's text turns white and moves 12 px right, its "
                        'number turns teal, and a violet-blue-teal underline grows across it. Hover or click '
                        'moves the signal to that stage and holds it there; leaving lets the cycle carry on. '
                        'As the camera arrives and leaves: like the hero (HTML on the section, which scrolls '
                        'with the curtain).',
    'scene_behaviour': 'Idle: the signal sphere and its trail go round the ring clockwise like the landing '
                       '(1.8 s per stage, eased settle at each stage); the stage it reaches lights in its colour '
                       '(#9B6BC4, #6F9CC6, #3FA9B8, #2FC4BA) with a glow. Cursor: only the Catalyst mark tilts '
                       'and lifts a little; the ring does not. The current parts around the cursor (same at '
                       'every stop). Arrives frozen and black and white; colour and motion once live.',
    'current': 'Arrives from below, goes around the outside of the ring and leaves through the left of the screen.',
    'media': "The Catalyst mark from the site (the landing's CycleCore SVG) in 3D, with its violet-blue-cyan "
             'glowing core. Ring, stage dots (spheres), signal, trail and glows built in 3D.',
    'transition_in': 'tilt up, same move as before (half circle radius 8, 60 degrees, travel 8)',
}
ENTER = {'tilt': 'up', 'tilt_degrees': 60, 'radius': 8.0, 'travel': 8.0}

CAMERA_AT = (0.0, -11.0, 0.0)
CAMERA_LENS = 28
FRAME = (1616, 875)
REST_DEPTH = 11.0

# ---- The ring (landing: CreativeCycleEngine, 1 px ring at 14% white, 16 px stage dots,
# 8 px signal, a 140-degree trail behind it, the mark at 21% of the ring's width) ----------
RING_CENTRE = (0.285, 0.5)     # in the frame (0..1 from the top-left)
RING_RADIUS = 0.29             # as a share of the frame height
STAGES = ['Strategy', 'Testing', 'Iteration', 'Scale']   # clockwise from the top
STAGE_COLORS = ['#9B6BC4', '#6F9CC6', '#3FA9B8', '#2FC4BA']
STAGE_PX, SIGNAL_PX, RING_PX = 16, 8, 1.5                # landing sizes in px (ring height 508 px)
TRAIL_DEG = 140
SIGNAL_DEG = 10                # where the signal rests in the poster (degrees clockwise from the top)
MARK_SHARE = 0.21              # mark width / ring diameter
MARK_DEPTH = 0.12              # extrusion, as a share of the mark's width
CORE_SHARE = 136.34 / 603.5    # glowing core square / mark width (from the SVG)

# ---- Current: from below, around the outside of the ring, out through the left ----------
FLOW = {'particles': 9000, 'width': 0.196, 'fibres': 34, 'speed': 0.48, 'twist': 9.0, 'samples': 220,
        'color': ('#a4a4aa', '#e2e2e6')}
CURRENT_RADIUS = 1.45          # path radius / ring radius
PARTICLE_RADIUS = 0.0055

GREYS = {'Ring': 0.05, 'Disc': 0.0015, 'Stage': 0.12, 'Signal': 1.0, 'Trail': 0.25, 'Mark': 0.75, 'Core': 0.2}


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



# ---- Ring geometry (all in the plane depth 11 ahead of the camera) ------------------------
px = FRAME_H * REST_DEPTH / FRAME[1]                       # one frame pixel, in scene units
centre = screen_point(*RING_CENTRE, REST_DEPTH)
radius = RING_RADIUS * FRAME_H * REST_DEPTH
mats = {name: emission(name, (g, g, g)) for name, g in GREYS.items()}
objects = []


def on_ring(deg, r=None):
    """Point on the ring, degrees clockwise from the top as seen from the camera."""
    a = math.radians(deg)
    return centre + Vector((math.sin(a), 0, math.cos(a))) * (radius if r is None else r)


def torus(name, major, minor, material, arc_deg=360.0, start_deg=0.0, segments=256, sides=12):
    """Ring (or arc) around `centre` in the camera-facing plane; arcs run clockwise from start_deg."""
    verts, faces = [], []
    steps = max(8, int(segments * arc_deg / 360))
    closed = arc_deg >= 360
    rings = steps if closed else steps + 1
    for i in range(rings):
        deg = start_deg + arc_deg * i / steps
        a = math.radians(deg)
        out = Vector((math.sin(a), 0, math.cos(a)))
        for j in range(sides):
            b = 2 * math.pi * j / sides
            verts.append(centre + out * (major + minor * math.cos(b)) + Vector((0, minor * math.sin(b), 0)))
    for i in range(steps):
        for j in range(sides):
            a0, a1 = i * sides + j, i * sides + (j + 1) % sides
            b0, b1 = ((i + 1) % rings) * sides + j, ((i + 1) % rings) * sides + (j + 1) % sides
            faces.append((a0, a1, b1, b0))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([tuple(v) for v in verts], [], faces)
    mesh.materials.append(material)
    ob = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(ob)
    return ob


def sphere(name, location, r, material):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=r, location=location)
    ob = bpy.context.active_object
    ob.name = name
    ob.data.materials.append(material)
    bpy.ops.object.shade_smooth()
    return ob


objects.append(torus('Ring', radius, RING_PX * px / 2, mats['Ring']))
bpy.ops.mesh.primitive_circle_add(vertices=128, radius=radius, fill_type='TRIFAN', location=centre + Vector((0, 0.02, 0)),
                                  rotation=(math.radians(90), 0, 0))
disc = bpy.context.active_object
disc.name = 'Disc'
disc.data.materials.append(mats['Disc'])
objects.append(disc)
stages = []
for i, label in enumerate(STAGES):
    p = on_ring(i * 90)
    objects.append(sphere(f'Stage_{i}', p, STAGE_PX * px / 2, mats['Stage']))
    stages.append({'label': label, 'deg': i * 90, 'color': STAGE_COLORS[i], 'centre': y_up(p)})
objects.append(sphere('Signal', on_ring(SIGNAL_DEG), SIGNAL_PX * px / 2, mats['Signal']))
objects.append(torus('Trail', radius, RING_PX * px * 0.9, mats['Trail'], arc_deg=TRAIL_DEG, start_deg=SIGNAL_DEG - TRAIL_DEG))

# The mark: core.svg's outline, extruded, facing the camera; the glowing core square inside it.
for addon in ('io_curve_svg',):
    try:
        bpy.ops.preferences.addon_enable(module=addon)
    except Exception:
        pass
before = set(bpy.data.objects)
bpy.ops.import_curve.svg(filepath=str(OUT / 'core.svg'))
curves = [o for o in bpy.data.objects if o not in before and o.type == 'CURVE']
mark = curves[0]
for o in curves[1:]:
    bpy.data.objects.remove(o)
bpy.context.view_layer.objects.active = mark
mark.select_set(True)
bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
width_now = mark.dimensions.x
mark_w = MARK_SHARE * 2 * radius
scale = mark_w / width_now
mark.data.extrude = MARK_DEPTH * mark_w / scale / 2
mark.data.dimensions = '2D'
mark.data.fill_mode = 'BOTH'
mark.scale = (scale, scale, scale)
mark.rotation_euler = (math.radians(90), 0, 0)             # SVG plane (XY) -> facing the camera (XZ)
mark.location = centre
bpy.ops.object.convert(target='MESH')
mark.name = 'Mark'
mark.data.materials.clear()
mark.data.materials.append(mats['Mark'])
bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
objects.append(mark)
core = plane('Core', CORE_SHARE * mark_w, CORE_SHARE * mark_w, mats['Core'])
core.location = centre + Vector((0, MARK_DEPTH * mark_w * 0.1, 0))
objects.append(core)

ring = {'centre': y_up(centre), 'radius': round(radius, 4), 'px': round(px, 6), 'frame_centre': list(RING_CENTRE),
        'radius_share_of_height': RING_RADIUS, 'stages': stages, 'signal_deg': SIGNAL_DEG, 'trail_deg': TRAIL_DEG,
        'stage_seconds': 1.8, 'mark_width': round(mark_w, 4), 'core_width': round(CORE_SHARE * mark_w, 4)}

# Current path: in from below (off screen); seen from the camera it climbs the right side,
# crosses over the top and runs down the left, then turns out through the left edge of the screen.
R = CURRENT_RADIUS * radius
path = [screen_point(RING_CENTRE[0] + 0.16, 1.18, 9.0), screen_point(RING_CENTRE[0] + 0.15, 0.98, 10.2)]
for deg, back in [(150, 0.5), (120, 0.2), (90, -0.2), (60, 0.0), (30, 0.4), (0, 0.6), (-30, 0.4),
                  (-60, 0.0), (-90, -0.3), (-115, 0.0)]:
    path.append(on_ring(deg, R) + Vector((0, back, 0)))
path += [screen_point(0.05, 0.66, 10.4), screen_point(-0.12, 0.62, 9.4)]

# ---- Current ----------------------------------------------------------------------
flow_paths_v, flow_rows, still = make_current(
    [(path, FLOW['particles'], FLOW['width'], FLOW['fibres'], FLOW['speed'])],
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
    'id': '04-cycle',
    'blender': bpy.app.version_string,
    'rest': {'position': y_up(camera.location), 'quaternion': [round(v, 6) for v in (q.x, q.y, q.z, q.w)],
             'horizontal_fov_deg': round(math.degrees(2 * math.atan(cam_data.sensor_width / 2 / cam_data.lens)), 3),
             'design_aspect': round(FRAME[0] / FRAME[1], 4)},
    'enter': ENTER,
    'brief': BRIEF,
    'ring': ring,
    'flow': {'file': 'flow.bin', 'count': len(flow_rows), 'floats_per_point': 11,
             'layout': ['path', 't', 'radius', 'angle', 'jitter_n', 'jitter_b', 'size', 'r', 'g', 'b', 'seed'],
             'samples': FLOW['samples'], 'twist': FLOW['twist'],
             'paths': [{'length': round(p['length'], 4), 'speed': p['speed'], 'points': [y_up(v) for v in p['points']],
                        'normals': [y_up(v) for v in p['normals']], 'binormals': [y_up(v) for v in p['binormals']]}
                       for p in flow_paths_v]},
}, indent=1))
print(f'STOP_DONE 04-cycle objects={len(objects)} flow={len(flow_rows)}')
