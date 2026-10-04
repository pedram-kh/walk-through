// Stop 02, clients ("Creative for" logo grid). The grid comes from Blender as three merged
// meshes (Cells, Lines, Words) whose vertices carry their cell number (_cell), so one draw
// call each covers all ten cells and the shaders light and lift one cell at a time.
// Hover, like the catalyst-growth.com logo grid: the cell lifts toward the camera, a violet
// glow fades in from its top-left corner, its hairlines turn into a rotating violet-blue-teal
// gradient, its wordmark goes full white and the other wordmarks dim. The current (the only
// particles here) parts around the cursor, as at stop 01. Monochrome apart from the hover.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { GREY_GLSL } from '../../runtime/materials.js';
import { createCurrent } from '../../runtime/flow.js';

const CONFIG = {
  lift: 0.35,                 // how far the hovered cell rises toward the camera (scene units)
  spring: { stiffness: 60, damping: 12 },
  fade: { in: 0.18, out: 0.35 },      // hover light time constants (s), like the site's 0.5 s / 0.75 s fades
  turnSeconds: 2,             // the border gradient's rotation while hovered (the site's 2 s)
  wordRest: 0.72, wordHover: 1, wordDim: 0.36,   // wordmark brightness: normal, hovered, others while one is hovered
  glow: 0.4,                  // violet glow strength at the corner (the site's 40%)
  current: { radius: 1.25, push: 0.6, swirl: 0.45, trail: 0.35, sizeBoost: 1.9 },   // cursor parting, as at stop 01
};

// The site's gradient: violet hsl(280,41%,43%), blue hsl(208,34%,50%), teal hsl(177,100%,30%),
// as a conic sweep violet-blue-teal-blue-teal-violet.
const GRADIENT_GLSL = /* glsl */`
const vec3 VIOLET = vec3(0.2038, 0.0524, 0.3259);
const vec3 BLUE = vec3(0.0890, 0.2247, 0.4064);
const vec3 TEAL = vec3(0.0000, 0.3185, 0.2846);
vec3 sweep(float t) {               // t in 0..1 around the cell
  float k = fract(t) * 5.0;
  if (k < 1.0) return mix(VIOLET, BLUE, k);
  if (k < 2.0) return mix(BLUE, TEAL, k - 1.0);
  if (k < 3.0) return mix(TEAL, BLUE, k - 2.0);
  if (k < 4.0) return mix(BLUE, TEAL, k - 3.0);
  return mix(TEAL, VIOLET, k - 4.0);
}`;

const CELL_VERTEX = /* glsl */`
attribute float _cell;
uniform float uLift[10];
varying vec2 vUv; varying vec3 vLocal; varying float vCell;
void main() {
  vCell = _cell;
  vUv = uv; vLocal = position;
  vec3 p = position + vec3(0.0, 0.0, uLift[int(_cell + 0.5)]);
  gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
}`;

const HOVER_UNIFORMS = /* glsl */`
uniform float uHover[10]; uniform float uAny; uniform float uAngle;
uniform vec3 uCentre[10]; uniform vec2 uSize[10];
varying vec2 vUv; varying vec3 vLocal; varying float vCell;
${GREY_GLSL}
${GRADIENT_GLSL}`;

// Cell panel: dark, with the violet glow from the top-left corner when hovered.
const CELL_FRAGMENT = /* glsl */`
uniform vec3 uBase; uniform float uGlow;
${HOVER_UNIFORMS}
void main() {
  int c = int(vCell + 0.5);
  vec2 size = uSize[c];
  float fromCorner = length(vUv * size) / length(size);       // uv (0,0) is the cell's top-left corner
  vec3 col = uBase + VIOLET * uGlow * (1.0 - clamp(fromCorner, 0.0, 1.0)) * uHover[c];
  gl_FragColor = vec4(toGrey(col), 1.0);
  #include <colorspace_fragment>
}`;

// Hairlines: grey, turning into the rotating gradient around the hovered cell.
const LINE_FRAGMENT = /* glsl */`
uniform vec3 uBase;
${HOVER_UNIFORMS}
void main() {
  int c = int(vCell + 0.5);
  vec2 d = (vLocal.xy - uCentre[c].xy) / uSize[c];
  float around = atan(d.y, d.x) / 6.2831853 + 0.5 + uAngle;
  vec3 col = mix(uBase, sweep(around), uHover[c]);
  gl_FragColor = vec4(toGrey(col), 1.0);
  #include <colorspace_fragment>
}`;

// Wordmarks: white at 72%, full white when hovered, dimmed while another cell is hovered.
const WORD_FRAGMENT = /* glsl */`
uniform float uRest, uHot, uDim;
${HOVER_UNIFORMS}
void main() {
  int c = int(vCell + 0.5);
  float level = mix(mix(uRest, uDim, uAny), uHot, uHover[c]);
  vec3 col = vec3(level * level);                              // white at that opacity over black, in linear
  gl_FragColor = vec4(toGrey(col), 1.0);
  #include <colorspace_fragment>
}`;

export async function load(ctx) {
  const fetchAs = async (file, kind) => {
    const response = await fetch(ctx.dir + file);
    if (!response.ok) throw Error('Missing stop 02 asset: ' + file);
    return response[kind]();
  };
  const [contract, gltf, flowBuffer] = await Promise.all([
    fetchAs('stop.json', 'json'), new GLTFLoader().loadAsync(ctx.dir + 'stop.glb'), fetchAs('flow.bin', 'arrayBuffer'),
  ]);
  const { camera } = ctx;
  const cells = contract.cells;
  const count = cells.length;
  const group = new THREE.Group();
  const grey = { value: 0 }, time = { value: 0 };

  // ---- Grid: one shared set of hover uniforms for the three meshes ---------------
  const hover = new Float32Array(count), lift = new Float32Array(count), liftVelocity = new Float32Array(count);
  const shared = {
    uGrey: grey, uHover: { value: hover }, uLift: { value: lift }, uAny: { value: 0 }, uAngle: { value: 0 },
    uCentre: { value: cells.map(c => new THREE.Vector3().fromArray(c.centre)) },
    uSize: { value: cells.map(c => new THREE.Vector2(c.width, c.height)) },
  };
  const shader = (fragmentShader, extra) => new THREE.ShaderMaterial({
    uniforms: { ...shared, ...extra }, vertexShader: CELL_VERTEX, fragmentShader, side: THREE.DoubleSide,
  });
  const linear = rgb => new THREE.Color().setRGB(...rgb);
  const materials = {
    Cells: shader(CELL_FRAGMENT, { uBase: { value: linear(contract.colors.cell) }, uGlow: { value: CONFIG.glow } }),
    Lines: shader(LINE_FRAGMENT, { uBase: { value: linear(contract.colors.line) } }),
    Words: shader(WORD_FRAGMENT, { uRest: { value: CONFIG.wordRest }, uHot: { value: CONFIG.wordHover }, uDim: { value: CONFIG.wordDim } }),
  };
  for (const name of Object.keys(materials)) {
    const mesh = gltf.scene.getObjectByName(name);
    if (!mesh?.isMesh || !mesh.geometry.getAttribute('_cell')) throw Error(`stop.glb: ${name} mesh or its _cell attribute is missing`);
    mesh.material = materials[name];
    group.add(mesh);
  }

  // ---- The current, parted by the cursor -----------------------------------------
  const pointerUniforms = {
    uTime: time, uScale: { value: 1 }, uActive: { value: 0 },
    uRadius: { value: CONFIG.current.radius }, uPush: { value: CONFIG.current.push }, uSwirl: { value: CONFIG.current.swirl },
    uTrail: { value: CONFIG.current.trail }, uSizeBoost: { value: CONFIG.current.sizeBoost }, uDrift: { value: 0 },
    uRayO: { value: new THREE.Vector3() }, uRayD: { value: new THREE.Vector3(0, 0, -1) },
    uTrailO: { value: new THREE.Vector3() }, uTrailD: { value: new THREE.Vector3(0, 0, -1) },
  };
  const current = createCurrent(contract.flow, flowBuffer, pointerUniforms);
  group.add(current.points);

  // ---- Hover: which cell the cursor is over (rays against the cells' rectangles) ----
  const raycaster = new THREE.Raycaster(), trailCaster = new THREE.Raycaster();
  const target = new THREE.Vector2(), fast = new THREE.Vector2(), slow = new THREE.Vector2();
  const inverse = new THREE.Matrix4(), localRay = new THREE.Ray();
  function hoveredCell() {
    if (!ctx.pointer.inside) return -1;
    localRay.copy(raycaster.ray).applyMatrix4(inverse.copy(group.matrixWorld).invert());
    let best = -1, nearest = Infinity;
    cells.forEach((cell, i) => {
      const z = cell.centre[2] + lift[i];
      const t = (z - localRay.origin.z) / localRay.direction.z;
      if (!(t > 0) || t >= nearest) return;
      const x = localRay.origin.x + localRay.direction.x * t, y = localRay.origin.y + localRay.direction.y * t;
      if (Math.abs(x - cell.centre[0]) <= cell.width / 2 && Math.abs(y - cell.centre[1]) <= cell.height / 2) { best = i; nearest = t; }
    });
    return best;
  }

  function animate(dt) {
    const { pointer } = ctx;
    target.set(pointer.x, pointer.y);
    time.value += dt;
    fast.lerp(target, 1 - Math.exp(-dt * 10));
    slow.lerp(target, 1 - Math.exp(-dt * 2.2));
    const presence = pointerUniforms.uActive;
    presence.value += ((pointer.inside ? 1 : 0) - presence.value) * (1 - Math.exp(-dt * (pointer.inside ? 6 : 2)));
    group.updateMatrixWorld(true);
    raycaster.setFromCamera(fast, camera);
    trailCaster.setFromCamera(slow, camera);
    pointerUniforms.uRayO.value.copy(raycaster.ray.origin); pointerUniforms.uRayD.value.copy(raycaster.ray.direction);
    pointerUniforms.uTrailO.value.copy(trailCaster.ray.origin); pointerUniforms.uTrailD.value.copy(trailCaster.ray.direction);

    raycaster.setFromCamera(target, camera);         // hover follows the cursor exactly
    const hot = hoveredCell();
    let any = 0;
    for (let i = 0; i < count; i++) {
      const on = i === hot ? 1 : 0;
      hover[i] += (on - hover[i]) * (1 - Math.exp(-dt / (on ? CONFIG.fade.in : CONFIG.fade.out)));
      any = Math.max(any, hover[i]);
      const { stiffness, damping } = CONFIG.spring;
      liftVelocity[i] += (stiffness * (CONFIG.lift * on - lift[i]) - damping * liftVelocity[i]) * dt;
      lift[i] += liftVelocity[i] * dt;
    }
    shared.uAny.value = any;
    if (hot >= 0) shared.uAngle.value += dt / CONFIG.turnSeconds;
    return hot >= 0 || any > 0.001 || lift.some(v => Math.abs(v) > 1e-4);
  }

  let frozen = true;
  return {
    group,
    counts: { cells: count, flow: contract.flow.count },
    setFrozen(value) { frozen = value; },
    setGrey(value) { grey.value = value; },
    setVisible() {},
    resize({ pixelScale }) { pointerUniforms.uScale.value = pixelScale; },
    // While live the current flows every frame.
    update(dt) {
      if (frozen) return false;
      animate(dt);
      return true;
    },
    dispose() {
      group.traverse(o => o.geometry?.dispose());
      Object.values(materials).forEach(m => m.dispose());
      current.dispose();
    },
  };
}
