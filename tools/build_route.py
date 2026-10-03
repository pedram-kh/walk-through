"""Route builder: joins the stops into one camera path (Blender 4.5 LTS, mathutils).

Run after any stop's build.py:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python tools/build_route.py
Reads stops/<id>/stop.json in the order of STOPS and writes route.json.

All maths here is in three.js axes (Y up, cameras look down -Z). Stop 01 sits at
the world origin. Every later stop says in its stop.json how the camera reaches
it ('enter'): from the previous stop's rest view the camera curls forward `curl`
units while tilting 90 degrees (down, up, left or right), then travels `travel`
units along its new view direction. The stop is then placed in the world so the
camera lands exactly on that stop's own rest view.
"""
import json, math
from pathlib import Path
from mathutils import Vector, Quaternion

ROOT = Path(__file__).resolve().parent.parent
STOPS = ['01-hero', '02-placeholder']      # route order
SAMPLES = 120                              # camera samples per segment
SPACER_SCREENS = 3.0                       # scroll length of each journey, in screen heights


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
    """Camera samples from a rest view (pos, rot) through the curl and travel."""
    forward, up, right = rot @ Vector((0, 0, -1)), rot @ Vector((0, 1, 0)), rot @ Vector((1, 0, 0))
    axis, angle, side = {
        'down':  (right, -1, -up),
        'up':    (right, 1, up),
        'left':  (up, 1, -right),
        'right': (up, -1, right),
    }[enter['tilt']]
    curl, travel = enter['curl'], enter['travel']
    arc = curl * math.pi / 2                     # length of the quarter-circle curl
    split = arc / (arc + travel)                 # constant speed through the hand-over
    positions, rotations = [], []
    for k in range(SAMPLES):
        u = smoothstep(k / (SAMPLES - 1))        # eased in and out over the whole journey
        if u < split:
            theta = math.pi / 2 * (u / split)
            p = pos + forward * curl * math.sin(theta) + side * curl * (1 - math.cos(theta))
            r = Quaternion(axis, angle * theta) @ rot
        else:
            p = pos + forward * curl + side * (curl + travel * (u - split) / (1 - split))
            r = Quaternion(axis, angle * math.pi / 2) @ rot
        positions.append(p)
        rotations.append(r)
    return positions, rotations


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

(ROOT / 'route.json').write_text(json.dumps(route, indent=1))
print('ROUTE_DONE', len(route['stops']), 'stops', len(route['segments']), 'segments')
for s in route['stops']:
    print(' ', s['id'], 'origin', s['origin'], 'rest', s['rest']['position'])
