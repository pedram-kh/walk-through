// Stop 03, the problem ("AI moves fast") - graybox: the three rows of cards from stop.glb
// in flat greys, and the stop's current (two strands around the card block), parted by
// the cursor as at every stop. Drifting rows, photos and the hero-style card tilt come
// after the graybox is approved (PLAN.md, step 5).
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { addGrey } from '../../runtime/materials.js';
import { createCurrent } from '../../runtime/flow.js';

const CURRENT = { radius: 1.25, push: 0.6, swirl: 0.45, trail: 0.35, sizeBoost: 1.9 };   // cursor parting, as at stop 01

export async function load(ctx) {
  const fetchAs = async (file, kind) => {
    const response = await fetch(ctx.dir + file);
    if (!response.ok) throw Error('Missing stop 03 asset: ' + file);
    return response[kind]();
  };
  const [contract, gltf, flowBuffer] = await Promise.all([
    fetchAs('stop.json', 'json'), new GLTFLoader().loadAsync(ctx.dir + 'stop.glb'), fetchAs('flow.bin', 'arrayBuffer'),
  ]);
  const { camera } = ctx;
  const grey = { value: 0 }, time = { value: 0 };
  const color = rgb => new THREE.Color().setRGB(...rgb);
  const materials = {
    Card: addGrey(new THREE.MeshBasicMaterial({ color: color(contract.colors.card), side: THREE.DoubleSide }), grey),
    Edge: addGrey(new THREE.MeshBasicMaterial({ color: color([0.0072, 0.0072, 0.0072]), side: THREE.DoubleSide }), grey),
    Chip: addGrey(new THREE.MeshBasicMaterial({ color: color(contract.colors.chip), side: THREE.DoubleSide }), grey),
  };
  const group = gltf.scene;
  group.traverse(o => { if (o.isMesh) o.material = materials[o.name.split('_')[0]] ?? materials.Card; });

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
    counts: { cards: contract.cards.length, flow: contract.flow.count },
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
