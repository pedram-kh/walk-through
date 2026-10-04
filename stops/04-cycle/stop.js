// Stop 04, the creative cycle - graybox: the ring, the four stage spheres, the signal and its
// trail, and the Catalyst mark from stop.glb in flat greys, and the stop's current (around the
// ring and out to the left), parted by the cursor as at every stop. The signal's run round the
// ring, the stage colours, the row buttons and the mark's tilt come after the graybox is
// approved (PLAN.md, step 5).
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { addGrey } from '../../runtime/materials.js';
import { createCurrent } from '../../runtime/flow.js';

const CURRENT = { radius: 1.25, push: 0.6, swirl: 0.45, trail: 0.35, sizeBoost: 1.9 };   // cursor parting, as at stop 01
const GREYS = { Ring: 0.05, Disc: 0.0015, Stage: 0.12, Signal: 1, Trail: 0.25, Mark: 0.75, Core: 0.2 };   // as build.py

export async function load(ctx) {
  const fetchAs = async (file, kind) => {
    const response = await fetch(ctx.dir + file);
    if (!response.ok) throw Error('Missing stop 04 asset: ' + file);
    return response[kind]();
  };
  const [contract, gltf, flowBuffer] = await Promise.all([
    fetchAs('stop.json', 'json'), new GLTFLoader().loadAsync(ctx.dir + 'stop.glb'), fetchAs('flow.bin', 'arrayBuffer'),
  ]);
  const { camera } = ctx;
  const grey = { value: 0 }, time = { value: 0 };
  const materials = Object.fromEntries(Object.entries(GREYS).map(([name, g]) =>
    [name, addGrey(new THREE.MeshBasicMaterial({ color: new THREE.Color().setRGB(g, g, g), side: THREE.DoubleSide }), grey)]));
  const group = gltf.scene;
  group.traverse(o => { if (o.isMesh) o.material = materials[o.name.split('_')[0]] ?? materials.Ring; });

  const uniforms = {
    uTime: time, uScale: { value: 1 }, uActive: { value: 0 },
    uRadius: { value: CURRENT.radius }, uPush: { value: CURRENT.push }, uSwirl: { value: CURRENT.swirl },
    uTrail: { value: CURRENT.trail }, uSizeBoost: { value: CURRENT.sizeBoost }, uDrift: { value: 0 },
    uRayO: { value: new THREE.Vector3() }, uRayD: { value: new THREE.Vector3(0, 0, -1) },
    uTrailO: { value: new THREE.Vector3() }, uTrailD: { value: new THREE.Vector3(0, 0, -1) },
  };
  const current = createCurrent(contract.flow, flowBuffer, uniforms);
  group.add(current.points);

  const raycaster = new THREE.Raycaster(), trailCaster = new THREE.Raycaster();
  const target = new THREE.Vector2(), fast = new THREE.Vector2(), slow = new THREE.Vector2();
  let frozen = true;
  return {
    group,
    counts: { stages: contract.ring.stages.length, flow: contract.flow.count },
    setFrozen(value) { frozen = value; },
    setGrey(value) { grey.value = value; },
    setVisible() {},
    resize({ pixelScale }) { uniforms.uScale.value = pixelScale; },
    update(dt) {
      if (frozen) return false;
      const { pointer } = ctx;
      time.value += dt;
      target.set(pointer.x, pointer.y);
      fast.lerp(target, 1 - Math.exp(-dt * 10));
      slow.lerp(target, 1 - Math.exp(-dt * 2.2));
      uniforms.uActive.value += ((pointer.inside ? 1 : 0) - uniforms.uActive.value) * (1 - Math.exp(-dt * (pointer.inside ? 6 : 2)));
      raycaster.setFromCamera(fast, camera);
      trailCaster.setFromCamera(slow, camera);
      uniforms.uRayO.value.copy(raycaster.ray.origin); uniforms.uRayD.value.copy(raycaster.ray.direction);
      uniforms.uTrailO.value.copy(trailCaster.ray.origin); uniforms.uTrailD.value.copy(trailCaster.ray.direction);
      return true;
    },
    dispose() {
      group.traverse(o => o.geometry?.dispose());
      Object.values(materials).forEach(m => m.dispose());
      current.dispose();
    },
  };
}
