// Stop 02, clients ("Creative for" logo grid) - graybox: cells, hairlines and wordmarks
// from stop.glb in flat greys, plus the stop's dust and current. The hover effect and
// cursor reactions are added after the graybox is approved (PLAN.md, step 5).
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { addGrey } from '../../runtime/materials.js';
import { DUST_VERTEX, POINT_FRAGMENT, createCurrent, stillPointerUniforms } from '../../runtime/flow.js';

export async function load(ctx) {
  const fetchAs = async (file, kind) => {
    const response = await fetch(ctx.dir + file);
    if (!response.ok) throw Error('Missing stop 02 asset: ' + file);
    return response[kind]();
  };
  const [contract, gltf, dustBuffer, flowBuffer] = await Promise.all([
    fetchAs('stop.json', 'json'), new GLTFLoader().loadAsync(ctx.dir + 'stop.glb'),
    fetchAs('dust.bin', 'arrayBuffer'), fetchAs('flow.bin', 'arrayBuffer'),
  ]);
  const grey = { value: 0 }, time = { value: 0 };
  const color = rgb => new THREE.Color().setRGB(...rgb);
  const materials = {
    Cell: addGrey(new THREE.MeshBasicMaterial({ color: color(contract.colors.cell), side: THREE.DoubleSide }), grey),
    Line: addGrey(new THREE.MeshBasicMaterial({ color: color(contract.colors.line), side: THREE.DoubleSide }), grey),
    Word: addGrey(new THREE.MeshBasicMaterial({ color: color(contract.colors.word), side: THREE.DoubleSide }), grey),
  };
  const group = gltf.scene;
  group.traverse(o => { if (o.isMesh) o.material = materials[o.name.split('_')[0]] ?? materials.Cell; });

  // Free dust around the grid.
  const raw = new Float32Array(dustBuffer), stride = contract.dust.floats_per_point, count = contract.dust.count;
  if (raw.length !== count * stride) throw Error('dust.bin does not match stop.json');
  const positions = new Float32Array(count * 3), colors = new Float32Array(count * 3);
  const sizes = new Float32Array(count), seeds = new Float32Array(count);
  for (let i = 0; i < count; i++) {
    const k = i * stride;
    positions.set([raw[k], raw[k + 1], raw[k + 2]], i * 3);
    colors.set([raw[k + 3], raw[k + 4], raw[k + 5]], i * 3);
    sizes[i] = raw[k + 6];
    seeds[i] = ((Math.sin(i * 12.9898) * 43758.5453) % 1 + 1) % 1;
  }
  const dustGeometry = new THREE.BufferGeometry();
  dustGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  dustGeometry.setAttribute('aColor', new THREE.BufferAttribute(colors, 3));
  dustGeometry.setAttribute('aSize', new THREE.BufferAttribute(sizes, 1));
  dustGeometry.setAttribute('aSeed', new THREE.BufferAttribute(seeds, 1));
  const uniforms = { ...stillPointerUniforms(time), uDrift: { value: 0.035 } };
  const dustMaterial = new THREE.ShaderMaterial({
    uniforms, vertexShader: DUST_VERTEX, fragmentShader: POINT_FRAGMENT,
    blending: THREE.AdditiveBlending, depthWrite: false, transparent: true,
  });
  const dust = new THREE.Points(dustGeometry, dustMaterial);
  dust.frustumCulled = false;
  group.add(dust);

  // The stop's current: continues the journey current and leaves on the left.
  const current = createCurrent(contract.flow, flowBuffer, uniforms);
  group.add(current.points);

  let frozen = true;
  return {
    group,
    counts: { cells: contract.cells.length, dust: count, flow: contract.flow.count },
    setFrozen(value) { frozen = value; },
    setGrey(value) { grey.value = value; },
    setVisible() {},
    resize({ pixelScale }) { uniforms.uScale.value = pixelScale; },
    update(dt) {
      if (frozen) return false;
      time.value += dt;
      return true;
    },
    dispose() {
      group.traverse(o => o.geometry?.dispose());
      Object.values(materials).forEach(m => m.dispose());
      dustMaterial.dispose(); current.dispose();
    },
  };
}
