// Stop 02, placeholder: grey slabs and a label from stop.glb, to test the route.
// Replaced when stop 02 is briefed and built.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { addGrey } from '../../runtime/materials.js';

export async function load(ctx) {
  const [contract, gltf] = await Promise.all([
    fetch(ctx.dir + 'stop.json').then(r => { if (!r.ok) throw Error('Missing stop 02 stop.json'); return r.json(); }),
    new GLTFLoader().loadAsync(ctx.dir + 'stop.glb'),
  ]);
  const grey = { value: 0 };
  const slab = addGrey(new THREE.MeshBasicMaterial({ color: new THREE.Color().setRGB(...contract.color) }), grey);
  const label = addGrey(new THREE.MeshBasicMaterial({ color: 0x9a9aa2 }), grey);
  const group = gltf.scene;
  group.traverse(o => { if (o.isMesh) o.material = o.name.startsWith('Label') ? label : slab; });
  return {
    group,
    counts: {},
    setFrozen() {},
    setGrey(value) { grey.value = value; },
    setVisible() {},
    resize() {},
    update() { return false; },
    dispose() {
      group.traverse(o => o.geometry?.dispose());
      slab.dispose(); label.dispose();
    },
  };
}
