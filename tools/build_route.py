"""Route builder: joins the stops into one camera path (Blender 4.5 LTS, mathutils).

Run after any stop's build.py:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python tools/build_route.py
Reads stops/<id>/stop.json in the order of STOPS and writes route.json.

All maths here is in three.js axes (Y up, cameras look down -Z). Stop 01 sits at
the world origin. Every later stop says in its stop.json how the camera reaches
it ('enter'): from the previous stop's rest view the camera rides a half circle
of `radius` units that swings toward that stop's objects (closest halfway round)
while tilting `tilt_degrees` (default 90) down, up, left or right, ending
2 x radius from where it started; then it travels `travel` units along its new
view direction. The
stop is then placed in the world so the camera lands exactly on its own rest view.
Every camera sample is checked against the objects in the stops' stop.glb files,
so the path never passes through a tile.

Journey currents: the particle current continues from stop to stop. Each segment
gets a current that picks up the previous stop's current where its main path
leaves the frame, runs a little ahead of the camera through the journey, and
hands over to the next stop's own current where it begins (or fades out near the
next stop if it has none). Written to currents/tNN.bin, described in route.json.
"""
import bpy, json, math, random, struct, sys
from pathlib import Path
from mathutils import Vector, Quaternion
from mathutils.bvhtree import BVHTree
sys.path.insert(0, str(Path(__file__).resolve().parent))
from flow_common import make_current

ROOT = Path(__file__).resolve().parent.parent
STOPS = ['01-hero', '02-clients']          # route order
SAMPLES = 240                              # camera samples per segment
SPACER_SCREENS = 2.0                       # scroll length of each journey's spacer, in screen heights
MIN_CLEARANCE = 0.8                        # closest the camera may pass to any object (tiles lift ~0.3 on hover)

# Journey current (matches stop 01's current: width, fibres, speed, twist, colour)
JOURNEY = {
    'ahead': 6.0,             # runs this far in front of the camera through the journey
    'offset': (0.7, -0.9),    # ...and this far right and below the centre of view, clear of the lens
    'times': (0.42, 0.55, 0.68, 0.8, 0.9),   # journey points it passes in front of the camera
    'end': (1.6, -1.4, -7.0), # if the next stop has no current: fade out here, in its camera frame
    'density': 300,           # particles per unit of length
    'width': 0.196, 'fibres': 34, 'speed': 0.48, 'twist': 9.0, 'samples': 200,
    'color': ('#a4a4aa', '#e2e2e6'), 'radius': 0.0055,
}
SEED = 11


def q3(q):                                 # mathutils (w, x, y, z) -> three.js [x, y, z, w]
    return [round(q.x, 6), round(q.y, 6), round(q.z, 6), round(q.w, 6)]


def v3(v):
    return [round(v.x, 5), round(v.y, 5), round(v.z, 5)]


def quat(xyzw):
    x, y, z, w = xyzw
    return Quaternion((w, x, y, z))


def smoothstep(t):
    return t * t * (3 - 2 * t)


def segment(pos, rot, enter):
    """Camera samples from a rest view (pos, rot): the half circle, then the travel."""
    forward, up, right = rot @ Vector((0, 0, -1)), rot @ Vector((0, 1, 0)), rot @ Vector((1, 0, 0))
    axis, angle, side = {
        'down':  (right, -1, -up),
        'up':    (right, 1, up),
        'left':  (up, 1, -right),
        'right': (up, -1, right),
    }[enter['tilt']]
    radius, travel = enter['radius'], enter['travel']
    tilt = math.radians(enter.get('tilt_degrees', 90))
    centre = pos + side * radius                 # circle in the plane of view and tilt
    arc = radius * math.pi                       # length of the half circle
    split = arc / (arc + travel)                 # constant speed through the hand-over
    positions, rotations = [], []
    for k in range(SAMPLES):
        u = smoothstep(k / (SAMPLES - 1))        # eased in and out over the whole journey
        if u < split:
            phi = math.pi * (u / split)          # 0 at rest, pi/2 closest to the objects, pi at the bottom
            p = centre - side * radius * math.cos(phi) + forward * radius * math.sin(phi)
            r = Quaternion(axis, angle * tilt * phi / math.pi) @ rot     # tilt spread evenly along the arc
        else:
            r = Quaternion(axis, angle * tilt) @ rot
            p = pos + side * 2 * radius + (r @ Vector((0, 0, -1))) * travel * (u - split) / (1 - split)
        positions.append(p)
        rotations.append(r)
    return positions, rotations


def linear(hex_color):
    h = hex_color.lstrip('#')
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]


def sample_at(positions, rotations, t):
    f = t * (len(positions) - 1)
    i = min(int(f), len(positions) - 2)
    return positions[i].lerp(positions[i + 1], f - i), rotations[i].slerp(rotations[i + 1], f - i)


def stop_current(stop):
    """A stop's main current path in world axes, or None."""
    contract = json.loads((ROOT / 'stops' / stop['id'] / 'stop.json').read_text())
    if 'flow' not in contract:
        return None
    origin, turn = Vector(stop['origin']), quat(stop['quaternion'])
    return [origin + turn @ Vector(v) for v in contract['flow']['paths'][0]['points']]


def journey_current(index, from_stop, to_stop, positions, rotations):
    """Current for segment `index`: from from_stop's main current to to_stop's."""
    tail = stop_current(from_stop)
    control = [tail[int(0.92 * (len(tail) - 1))], tail[-1]]      # overlap the tail so the hand-over is seamless
    dx, dy = JOURNEY['offset']
    for t in JOURNEY['times']:
        p, r = sample_at(positions, rotations, t)
        control.append(p + r @ Vector((dx, dy, -JOURNEY['ahead'])))
    head = stop_current(to_stop)
    if head:                                                    # overlap the next stop's current
        control += [head[0], head[int(0.08 * (len(head) - 1))]]
    else:
        control.append(positions[-1] + rotations[-1] @ Vector(JOURNEY['end']))
    rough = sum((b - a).length for a, b in zip(control, control[1:]))
    random.seed(SEED + index)
    paths, rows, _ = make_current(
        [(control, int(rough * JOURNEY['density']), JOURNEY['width'], JOURNEY['fibres'], JOURNEY['speed'])],
        facing=rotations[len(rotations) // 2] @ Vector((0, 0, -1)), samples=JOURNEY['samples'], amount=1.0,
        twist=JOURNEY['twist'], base=linear(JOURNEY['color'][0]), bright=linear(JOURNEY['color'][1]),
        radius=JOURNEY['radius'])
    (ROOT / 'currents').mkdir(exist_ok=True)
    name = f'currents/t{index + 1:02d}.bin'
    with open(ROOT / name, 'wb') as f:
        for row in rows:
            f.write(struct.pack('<11f', *row))
    return {
        'file': name, 'count': len(rows), 'floats_per_point': 11, 'samples': JOURNEY['samples'], 'twist': JOURNEY['twist'],
        'paths': [{'length': round(p['length'], 4), 'speed': p['speed'], 'points': [v3(v) for v in p['points']],
                   'normals': [v3(v) for v in p['normals']], 'binormals': [v3(v) for v in p['binormals']]} for p in paths],
    }, paths[0]['points']


def stop_objects(stop_id, origin, rotation):
    """BVH of a stop's stop.glb meshes, in world (three.js) axes."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(ROOT / 'stops' / stop_id / 'stop.glb'))
    verts, polys = [], []
    for ob in bpy.context.scene.objects:
        if ob.type != 'MESH':
            continue
        offset = len(verts)
        for v in ob.data.vertices:
            b = ob.matrix_world @ v.co                       # Blender Z-up after import
            verts.append(origin + rotation @ Vector((b.x, b.z, -b.y)))
        polys += [[offset + i for i in p.vertices] for p in ob.data.polygons]
    return BVHTree.FromPolygons(verts, polys) if polys else None


route = {'version': 1, 'stops': [], 'segments': []}
cam_pos = cam_rot = None
for index, stop_id in enumerate(STOPS):
    contract = json.loads((ROOT / 'stops' / stop_id / 'stop.json').read_text())
    rest = contract['rest']
    local_pos, local_rot = Vector(rest['position']), quat(rest['quaternion'])
    if index == 0:
        cam_pos, cam_rot = local_pos.copy(), local_rot.copy()      # stop 01 defines the world
        raw_segments = []
        route['camera'] = {'horizontal_fov_deg': rest['horizontal_fov_deg'], 'design_aspect': rest['design_aspect']}
    else:
        positions, rotations = segment(cam_pos, cam_rot, contract['enter'])
        route['segments'].append({
            'from': STOPS[index - 1], 'to': stop_id, 'tilt': contract['enter']['tilt'],
            'spacer': f't{index:02d}', 'spacer_screens': SPACER_SCREENS,
            'position': [v3(p) for p in positions], 'quaternion': [q3(r) for r in rotations],
        })
        raw_segments.append((positions, rotations))
        cam_pos, cam_rot = positions[-1], rotations[-1]
    # Place the stop so its own rest camera coincides with the route camera here.
    world_rot = cam_rot @ local_rot.inverted()
    world_pos = cam_pos - world_rot @ local_pos
    route['stops'].append({
        'id': stop_id, 'dir': f'stops/{stop_id}/', 'section': f's{index + 1:02d}',
        'origin': v3(world_pos), 'quaternion': q3(world_rot),
        'rest': {'position': v3(cam_pos), 'quaternion': q3(cam_rot)},
        'poster': f'stops/{stop_id}/poster.jpg',
    })

# Journey currents, and how visible each one is: from the rest view before it
# (should be ~0, so the approved composition is untouched) and during the journey.
tan_h = math.tan(math.radians(route['camera']['horizontal_fov_deg']) / 2)
tan_v = tan_h / route['camera']['design_aspect']
def in_view(p, r, w):
    v = r.inverted() @ (w - p)
    return v.z < -0.3 and abs(v.x / -v.z) < tan_h and abs(v.y / -v.z) < tan_v
for k, (seg, (positions, rotations)) in enumerate(zip(route['segments'], raw_segments)):
    seg['current'], line = journey_current(k, route['stops'][k], route['stops'][k + 1], positions, rotations)
    rest_seen = sum(in_view(positions[0], rotations[0], w) for w in line) / len(line)
    report = []
    for t in (0.3, 0.4, 0.5, 0.6, 0.7):
        p, r = sample_at(positions, rotations, t)
        report.append(f"{t:.0%} {sum(in_view(p, r, w) for w in line) / len(line):.0%}")
    print(f"  current {seg['current']['file']}: {seg['current']['count']} particles; seen from the rest view: {rest_seen:.0%}; "
          f"share in view during the journey: {', '.join(report)}")

# Clearance: the closest any camera sample comes to the objects of the stops it joins.
trees = {s['id']: stop_objects(s['id'], Vector(s['origin']), quat(s['quaternion'])) for s in route['stops']}
for seg in route['segments']:
    closest = min((tree.find_nearest(Vector(p))[3], stop_id) for stop_id in (seg['from'], seg['to'])
                  if (tree := trees[stop_id]) for p in seg['position'])
    seg['min_clearance'] = round(closest[0], 3)
    print(f"  {seg['from']} -> {seg['to']}: closest pass {closest[0]:.2f} units from {closest[1]}")
    if closest[0] < MIN_CLEARANCE:
        raise SystemExit(f'ROUTE_FAILED camera passes within {closest[0]:.2f} of {closest[1]}; increase the clearance')

(ROOT / 'route.json').write_text(json.dumps(route, indent=1))
print('ROUTE_DONE', len(route['stops']), 'stops', len(route['segments']), 'segments')
for s in route['stops']:
    print(' ', s['id'], 'origin', s['origin'], 'rest', s['rest']['position'])
