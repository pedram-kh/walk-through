"""Stop 02, placeholder - graybox only, to test the route (Blender 4.5 LTS).

Not a real stop yet: grey slabs and a label so the transition from stop 01 has
something to arrive at. Replaced when stop 02 is briefed and built.
Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python stops/02-placeholder/build.py
Outputs beside this file:
  poster.jpg, stop.blend     preview render (also the fallback poster) and editable scene
  stop.glb                   the slabs and label (names, rest transforms)
  stop.json                  contract: rest camera, how the route enters this stop, brief
"""
import bpy, json, math
from pathlib import Path
from mathutils import Vector, Matrix

OUT = Path(__file__).resolve().parent

BRIEF = {'status': 'placeholder for route testing, not briefed'}

# How the camera reaches this stop from the previous one (used by tools/build_route.py):
# a half circle of `radius` units that swings toward the previous stop's objects while
# tilting 90 degrees `tilt`, then a straight `travel` of that many units.
ENTER = {'tilt': 'down', 'radius': 8.0, 'travel': 14.0}

# Same camera and frame as stop 01, so every stop rests the same way.
CAMERA_AT = (0.0, -11.0, 0.0)
CAMERA_LENS = 28
FRAME = (1616, 875)
GREY = (0.18, 0.18, 0.2)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.resolution_x, scene.render.resolution_y = FRAME


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


slab_mat = emission('Slab grey', GREY)
objects = []
for row in range(3):                   # a plain 5 x 3 grid of thin slabs, facing the camera
    for col in range(5):
        bpy.ops.mesh.primitive_cube_add(size=1, location=((col - 2) * 2.2, 0, (1 - row) * 1.25 - 0.3))
        ob = bpy.context.active_object
        ob.name = f'Slab_{row}{col}'
        ob.scale = (2.0, 0.08, 1.05)
        ob.data.materials.append(slab_mat)
        objects.append(ob)

bpy.ops.object.text_add(location=(-5.4, -0.3, 1.7), rotation=(math.radians(90), 0, 0))
label = bpy.context.active_object
label.data.body = '02  PLACEHOLDER'
label.data.size = 0.36
label.data.materials.append(emission('Label', (0.6, 0.6, 0.64)))
bpy.ops.object.convert(target='MESH')
label.name = 'Label'
objects.append(label)

cam_data = bpy.data.cameras.new('Stop camera')
cam_data.lens = CAMERA_LENS
camera = bpy.data.objects.new('Stop camera', cam_data)
scene.collection.objects.link(camera)
camera.location = CAMERA_AT
camera.rotation_euler = (Vector((0, 0, 0)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = camera

world = bpy.data.worlds.new('Black')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs[0].default_value = (0.0006, 0.0006, 0.0012, 1)
scene.world = world
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 16
scene.cycles.use_denoising = False
scene.view_settings.view_transform = 'Standard'
scene.render.image_settings.file_format = 'JPEG'
scene.render.image_settings.quality = 85
scene.render.filepath = str(OUT / 'poster.jpg')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'stop.blend'))
bpy.ops.render.render(write_still=True)


def y_up(v):
    return [round(v[0], 5), round(v[2], 5), round(-v[1], 5)]


bpy.ops.object.select_all(action='DESELECT')
for ob in objects:
    ob.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(OUT / 'stop.glb'), export_format='GLB', use_selection=True,
                          export_materials='NONE', export_animations=False)

Y_UP = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0)))
q = (Y_UP @ camera.matrix_world.to_3x3()).to_quaternion()
(OUT / 'stop.json').write_text(json.dumps({
    'id': '02-placeholder',
    'blender': bpy.app.version_string,
    'rest': {'position': y_up(camera.location), 'quaternion': [round(v, 6) for v in (q.x, q.y, q.z, q.w)],
             'horizontal_fov_deg': round(math.degrees(2 * math.atan(cam_data.sensor_width / 2 / cam_data.lens)), 3),
             'design_aspect': round(FRAME[0] / FRAME[1], 4)},
    'enter': ENTER,
    'brief': BRIEF,
    'color': GREY,
}, indent=2))
print('STOP_DONE 02-placeholder objects', len(objects))
