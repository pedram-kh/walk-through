"""Route builder: joins the stops into one camera path (Blender 4.5 LTS, mathutils).

Run after any stop's build.py:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python tools/build_route.py
Reads stops/<id>/stop.json in the order of STOPS and writes route.json.

All maths here is in three.js axes (Y up, cameras look down -Z). Stop 01 sits at
the world origin. Every later stop says in its stop.json how the camera reaches
it ('enter'): from the previous stop's rest view the camera rides a half circle
of `radius` units that swings toward that stop's objects (closest halfway round)
while tilting 90 degrees (down, up, left or right), ending 2 x radius from where
it started; then it travels `travel` units along its new view direction. The
stop is then placed in the world so the camera lands exactly on its own rest view.
Every camera sample is checked against the objects in the stops' stop.glb files,
so the path never passes through a tile.
"""
import bpy, bmesh, json, math
from pathlib import Path
from mathutils import Vector, Quaternion, Matrix
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parent.parent
STOPS = ['01-hero', '02-placeholder']      # route order
SAMPLES = 120                              # camera samples per segment
SPACER_SCREENS = 3.0                       # scroll length of each journey, in screen heights
MIN_CLEARANCE = 0.8                        # closest the camera may pass to any object (tiles lift ~0.3 on hover)


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
    centre = pos + side * radius                 # circle in the plane of view and tilt
    arc = radius * math.pi                       # length of the half circle
    split = arc / (arc + travel)                 # constant speed through the hand-over
    positions, rotations = [], []
    for k in range(SAMPLES):
        u = smoothstep(k / (SAMPLES - 1))        # eased in and out over the whole journey
        if u < split:
            phi = math.pi * (u / split)          # 0 at rest, pi/2 closest to the objects, pi at the bottom
            p = centre - side * radius * math.cos(phi) + forward * radius * math.sin(phi)
            r = Quaternion(axis, angle * phi / 2) @ rot          # tilt 0 -> 90 degrees along the arc
        else:
            p = pos + side * (2 * radius + travel * (u - split) / (1 - split))
            r = Quaternion(axis, angle * math.pi / 2) @ rot
        positions.append(p)
        rotations.append(r)
    return positions, rotations


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
        route['camera'] = {'horizontal_fov_deg': rest['horizontal_fov_deg'], 'design_aspect': rest['design_aspect']}
    else:
        positions, rotations = segment(cam_pos, cam_rot, contract['enter'])
        route['segments'].append({
            'from': STOPS[index - 1], 'to': stop_id, 'tilt': contract['enter']['tilt'],
            'spacer': f't{index:02d}', 'spacer_screens': SPACER_SCREENS,
            'position': [v3(p) for p in positions], 'quaternion': [q3(r) for r in rotations],
        })
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
