// Stop 04, the creative cycle (landing section 13). The ring, its four stage spheres and
// their labels, the signal with its trail, the glows and the list's lines are built here from
// stop.json; the Catalyst mark comes from stop.glb. Like the landing: the signal runs clockwise
// round the ring, 1.8 s per stage with an eased settle at each one; the stage it has reached
// lights in its colour, and so do its label, its row and the row's underline. Hovering,
// focusing or clicking a row moves the signal to that stage and holds it there. The ring turns
// slowly on its vertical axis (labels and glows face the camera); the mark tilts and lifts a
// little near the cursor. Only the text is HTML: the lines under it are 3D, measured from the
// HTML rows, so the text leaves with the curtain and the lines stay with the scene.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { GREY_GLSL } from '../../runtime/materials.js';
import { createCurrent } from '../../runtime/flow.js';

const CONFIG = {
  current: { radius: 1.25, push: 0.6, swirl: 0.45, trail: 0.35, sizeBoost: 1.9 },   // as at stop 01
  mark: { reach: 0.55, tilt: 0.2, lift: 0.25, stiffness: 55, damping: 11 },        // hero tile spring, gentler
  stageMs: 1800,          // landing STAGE_MS
  fadeSeconds: 0.4,       // landing: transition .4s on the stage colours
  ringPx: 1, trailPx: 2,  // line widths in landing px (ring 1 px border, trail mask ~2 px)
  stagePx: 16, signalPx: 8,
  orbitSeconds: 30,       // one turn of the ring on its vertical axis
  labelPx: 11, labelOut: 42, labelSpacing: 0.12,   // landing: 11 px mono, 42 px out from the dot, .12em tracking
  underlineRate: 7,       // the active row's underline grows / shrinks (landing: .5s ease-out)
};
const DIM_RIM = [0.22, 0.22, 0.22], DIM_DOT = [0.28, 0.28, 0.28];   // landing rgba(255,255,255,.22 / .28) over black

const srgbToLinear = c => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const hexLinear = hex => [1, 3, 5].map(i => srgbToLinear(parseInt(hex.slice(i, i + 2), 16) / 255));

// ---- Shaders ----------------------------------------------------------------------
const PLAIN_VERTEX = /* glsl */`
varying vec2 vPos;
void main() { vPos = position.xy; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;

// The landing's CycleTrail: a conic gradient that ends at the signal, masked to the ring line.
const TRAIL_FRAGMENT = /* glsl */`
uniform float uSignal;          // radians clockwise from the top
varying vec2 vPos;
${GREY_GLSL}
void main() {
  float a = atan(vPos.x, vPos.y);                       // clockwise from the top
  float behind = mod(uSignal - a, 6.2831853);           // how far behind the signal
  float o = degrees(2.4434609 - behind);                // 0 at the tail .. 140 at the signal
  if (o < 0.0) discard;
  vec4 violet = vec4(0.608, 0.420, 0.769, 0.55), blue = vec4(0.435, 0.612, 0.776, 1.0), teal = vec4(0.184, 0.769, 0.729, 1.0);
  vec4 c = o < 50.0 ? mix(vec4(violet.rgb, 0.0), violet, o / 50.0) : o < 105.0 ? mix(violet, blue, (o - 50.0) / 55.0) : mix(blue, teal, (o - 105.0) / 35.0);
  gl_FragColor = vec4(toGrey(pow(c.rgb, vec3(2.2))), c.a);
  #include <colorspace_fragment>
}`;

// Behind the ring: the landing's outer glow (130% box, violet to blue) plus the ring's own faint
// fill. CSS mixes these over black in sRGB, so the sums are sRGB and converted at the end.
const HALO_FRAGMENT = /* glsl */`
uniform float uRadius;
varying vec2 vPos;
${GREY_GLSL}
void main() {
  float d = length(vPos) / uRadius;
  float q = d / 1.3;
  vec3 glow = q < 0.6 ? mix(vec3(0.35, 0.18, 0.62) * 0.12, vec3(0.12, 0.42, 0.50) * 0.04, q / 0.6)
                      : mix(vec3(0.12, 0.42, 0.50) * 0.04, vec3(0.0), clamp((q - 0.6) / 0.4, 0.0, 1.0));
  vec3 fill = d < 0.55 ? mix(vec3(0.482, 0.251, 0.6) * 0.07, vec3(0.329, 0.506, 0.663) * 0.03, d / 0.55)
                       : mix(vec3(0.329, 0.506, 0.663) * 0.03, vec3(0.0), clamp((d - 0.55) / 0.45, 0.0, 1.0));
  gl_FragColor = vec4(toGrey(pow(glow + fill, vec3(2.2))), 1.0);
  #include <colorspace_fragment>
}`;

// Stage spheres and the signal: a dark body with a coloured rim and a coloured centre, like the
// landing's 16 px dot (1 px border, 6 px inner dot), but round.
const SPHERE_VERTEX = /* glsl */`
attribute vec3 aRim, aDot, aBody;
varying vec3 vNormal, vRim, vDot, vBody;
void main() {
  vRim = aRim; vDot = aDot; vBody = aBody;
  vNormal = normalize(normalMatrix * mat3(instanceMatrix) * normal);
  gl_Position = projectionMatrix * modelViewMatrix * instanceMatrix * vec4(position, 1.0);
}`;
const SPHERE_FRAGMENT = /* glsl */`
varying vec3 vNormal, vRim, vDot, vBody;
${GREY_GLSL}
void main() {
  float facing = abs(normalize(vNormal).z);
  float rim = smoothstep(0.5, 0.15, facing);
  float centre = smoothstep(0.90, 0.95, facing);
  vec3 c = mix(mix(vBody, vRim, rim), vDot, centre) * (0.75 + 0.25 * facing);
  gl_FragColor = vec4(toGrey(c), 1.0);
  #include <colorspace_fragment>
}`;

// Soft glows (box-shadow 0 0 Npx) around the active stage and the signal.
const GLOW_VERTEX = /* glsl */`
attribute vec4 aGlow;           // rgb (linear), strength
attribute vec2 aShape;          // core radius, blur sigma (in quad units: the quad is 1 x 1)
varying vec2 vPos;
varying vec4 vGlow;
varying vec2 vShape;
void main() {
  vPos = position.xy; vGlow = aGlow; vShape = aShape;
  gl_Position = projectionMatrix * modelViewMatrix * instanceMatrix * vec4(position, 1.0);
}`;
const GLOW_FRAGMENT = /* glsl */`
varying vec2 vPos;
varying vec4 vGlow;
varying vec2 vShape;
${GREY_GLSL}
void main() {
  float d = length(vPos);
  float a = 1.0 - smoothstep(-2.0, 2.0, (d - vShape.x) / vShape.y);   // blurred disc
  gl_FragColor = vec4(toGrey(vGlow.rgb) * a * vGlow.a, 1.0);
  #include <colorspace_fragment>
}`;

// The mark: 92% white, its extruded sides a little darker so it reads as a solid.
const MARK_VERTEX = /* glsl */`
varying vec3 vNormal;
void main() { vNormal = normalize(normalMatrix * normal); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const MARK_FRAGMENT = /* glsl */`
varying vec3 vNormal;
${GREY_GLSL}
void main() {
  float facing = abs(normalize(vNormal).z);
  gl_FragColor = vec4(toGrey(vec3(0.83) * (0.55 + 0.45 * facing)), 1.0);
  #include <colorspace_fragment>
}`;

// The core inside the mark: core.svg's rounded square, a violet-blue-cyan gradient at 50%,
// darker towards the top, blurred twice (stdDeviation 37 and 7 of 604).
const CORE_FRAGMENT = /* glsl */`
uniform float uHalf, uWide, uNarrow;
varying vec2 vPos;
${GREY_GLSL}
float erfish(float x) { return tanh(1.2027 * x); }
float box(vec2 p, float s) {
  vec2 a = 0.5 * (vec2(erfish((p.x + uHalf) / (s * 1.4142)), erfish((p.y + uHalf) / (s * 1.4142)))
                - vec2(erfish((p.x - uHalf) / (s * 1.4142)), erfish((p.y - uHalf) / (s * 1.4142))));
  return a.x * a.y;
}
void main() {
  float u = clamp(vPos.x / (2.0 * uHalf) + 0.5, 0.0, 1.0), v = clamp(vPos.y / (2.0 * uHalf) + 0.5, 0.0, 1.0);
  vec3 g = u < 0.5 ? mix(vec3(0.804, 0.412, 1.0), vec3(0.498, 0.765, 1.0), u * 2.0)
                   : mix(vec3(0.498, 0.765, 1.0), vec3(0.0, 1.0, 0.949), u * 2.0 - 1.0);
  float top = 1.0 - 0.62 * v;                     // paint1: black at the top fading out downwards
  float a = max(box(vPos, uWide), box(vPos, uNarrow));
  gl_FragColor = vec4(toGrey(pow(g * 0.5 * top * a, vec3(2.2))), 1.0);   // mixed over black in sRGB, as the SVG
  #include <colorspace_fragment>
}`;

// The list's lines: 1 px at 14% white under each row and above the title; over each row line,
// the active row's violet-blue-teal underline, grown to uProgress[row] of its length.
const LINE_VERTEX = /* glsl */`
attribute float aU, aRow;
varying float vU, vRow;
void main() { vU = aU; vRow = aRow; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const LINE_FRAGMENT = /* glsl */`
uniform vec4 uProgress;
varying float vU, vRow;
${GREY_GLSL}
void main() {
  vec3 c = vec3(0.14);
  if (vRow > -0.5) {
    int i = int(vRow + 0.5);
    float p = i == 0 ? uProgress.x : i == 1 ? uProgress.y : i == 2 ? uProgress.z : uProgress.w;
    if (vU > p) discard;
    c = vU < 0.5 ? mix(vec3(0.482, 0.251, 0.6), vec3(0.329, 0.506, 0.663), vU * 2.0)
                 : mix(vec3(0.329, 0.506, 0.663), vec3(0.0, 0.6, 0.573), vU * 2.0 - 1.0);
  }
  gl_FragColor = vec4(toGrey(pow(c, vec3(2.2))), 1.0);
  #include <colorspace_fragment>
}`;

// Stage labels: one canvas texture, one instance per label, facing the camera.
const LABEL_VERTEX = /* glsl */`
attribute vec4 aCell;
attribute float aOn;
varying vec2 vUv;
varying float vOn;
void main() {
  vUv = aCell.xy + uv * aCell.zw; vOn = aOn;
  gl_Position = projectionMatrix * modelViewMatrix * instanceMatrix * vec4(position, 1.0);
}`;
const LABEL_FRAGMENT = /* glsl */`
uniform sampler2D uText;
varying vec2 vUv;
varying float vOn;
${GREY_GLSL}
void main() {
  float a = texture2D(uText, vUv).a;
  if (a < 0.01) discard;
  gl_FragColor = vec4(toGrey(vec3(pow(mix(0.5, 1.0, vOn), 2.2))), a);   // landing: 50% white, white when active
  #include <colorspace_fragment>
}`;

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
  const ring = contract.ring, px = ring.px, r = ring.radius;
  const grey = { value: 0 }, time = { value: 0 };
  const group = new THREE.Group();
  const centre = new THREE.Group();                      // everything sits around the ring's centre
  centre.position.fromArray(ring.centre);
  group.add(centre);
  const disposables = [];
  const own = (...things) => { disposables.push(...things); return things[0]; };
  const shader = (fragmentShader, uniforms = {}, options = {}) => own(new THREE.ShaderMaterial({
    uniforms: { uGrey: grey, ...uniforms }, vertexShader: PLAIN_VERTEX, fragmentShader, ...options }));

  // ---- Halo, ring and trail ----
  const halo = new THREE.Mesh(own(new THREE.PlaneGeometry(2.6 * r, 2.6 * r)),
    shader(HALO_FRAGMENT, { uRadius: { value: r } }, { transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
  halo.position.z = -0.03;
  halo.renderOrder = -2;
  const ringLine = new THREE.Mesh(own(new THREE.TorusGeometry(r, CONFIG.ringPx * px / 2, 6, 256)),
    own(new THREE.ShaderMaterial({ uniforms: { uGrey: grey }, vertexShader: PLAIN_VERTEX,
      fragmentShader: `${GREY_GLSL}\nvoid main() { gl_FragColor = vec4(toGrey(vec3(0.0168)), 1.0);\n#include <colorspace_fragment>\n}` })));
  const signalAngle = { value: THREE.MathUtils.degToRad(ring.signal_deg) };
  const trail = new THREE.Mesh(own(new THREE.TorusGeometry(r, CONFIG.trailPx * px / 2, 6, 256)),
    shader(TRAIL_FRAGMENT, { uSignal: signalAngle }, { transparent: true, depthWrite: false }));
  trail.position.z = 0.002;
  trail.renderOrder = 1;
  const orbit = new THREE.Group();                       // turns on its vertical axis
  orbit.add(ringLine, trail);
  centre.add(halo, orbit);

  // ---- Stage spheres and the signal (one instanced mesh), and their glows ----
  const stages = ring.stages.map(s => ({ ...s, linear: hexLinear(s.color), on: 0 }));
  const onRing = (deg, out) => out.set(Math.sin(THREE.MathUtils.degToRad(deg)) * r, Math.cos(THREE.MathUtils.degToRad(deg)) * r, 0);
  const sphereGeometry = own(new THREE.SphereGeometry(CONFIG.stagePx * px / 2, 32, 16));
  const count = stages.length + 1;                       // the last instance is the signal
  const rim = new Float32Array(count * 3), dot = new Float32Array(count * 3), body = new Float32Array(count * 3);
  for (const [name, array] of [['aRim', rim], ['aDot', dot], ['aBody', body]]) sphereGeometry.setAttribute(name, new THREE.InstancedBufferAttribute(array, 3));
  const spheres = new THREE.InstancedMesh(sphereGeometry, own(new THREE.ShaderMaterial({
    uniforms: { uGrey: grey }, vertexShader: SPHERE_VERTEX, fragmentShader: SPHERE_FRAGMENT })), count);
  spheres.frustumCulled = false;
  const glowGeometry = own(new THREE.PlaneGeometry(1, 1));
  const glowData = new Float32Array(count * 4), glowShape = new Float32Array(count * 2);
  glowGeometry.setAttribute('aGlow', new THREE.InstancedBufferAttribute(glowData, 4));
  glowGeometry.setAttribute('aShape', new THREE.InstancedBufferAttribute(glowShape, 2));
  const glows = new THREE.InstancedMesh(glowGeometry, own(new THREE.ShaderMaterial({
    uniforms: { uGrey: grey }, vertexShader: GLOW_VERTEX, fragmentShader: GLOW_FRAGMENT,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending })), count);
  glows.frustumCulled = false;
  glows.renderOrder = 2;
  orbit.add(spheres);
  centre.add(glows);
  const matrix = new THREE.Matrix4(), point = new THREE.Vector3(), unit = new THREE.Vector3(1, 1, 1), noTurn = new THREE.Quaternion();
  const stageGlowSize = (CONFIG.stagePx / 2 + 24) * px * 2, signalGlowSize = (CONFIG.signalPx / 2 + 20) * px * 2;
  stages.forEach((s, i) => {
    onRing(s.deg, point);
    spheres.setMatrixAt(i, matrix.compose(point, noTurn, unit));
    body.set(hexLinear('#050507'), i * 3);
    glowShape.set([CONFIG.stagePx / 2 * px / stageGlowSize, 6 * px / stageGlowSize], i * 2);   // 12 px blur ~ sigma 6
  });
  body.set([1, 1, 1], stages.length * 3); rim.set([1, 1, 1], stages.length * 3); dot.set([1, 1, 1], stages.length * 3);
  glowData.set([1, 1, 1, 0.45], stages.length * 4);
  glowShape.set([CONFIG.signalPx / 2 * px / signalGlowSize, 5 * px / signalGlowSize], stages.length * 2);

  // ---- The mark and its core, on a pivot that tilts and lifts near the cursor ----
  const pivot = new THREE.Group();
  centre.add(pivot);
  let markMesh = null;
  gltf.scene.traverse(o => { if (o.isMesh && o.name.startsWith('Mark')) markMesh = o; });
  if (!markMesh) throw Error('stop 04: no Mark in stop.glb');
  markMesh.removeFromParent();
  markMesh.position.set(0, 0, 0);
  markMesh.material = own(new THREE.ShaderMaterial({ uniforms: { uGrey: grey }, vertexShader: MARK_VERTEX, fragmentShader: MARK_FRAGMENT }));
  own(markMesh.geometry);
  const W = ring.mark_width, half = ring.core_width / 2;
  const core = new THREE.Mesh(own(new THREE.PlaneGeometry(2 * (half + 0.2 * W), 2 * (half + 0.2 * W))),
    shader(CORE_FRAGMENT, { uHalf: { value: half }, uWide: { value: 37 / 604 * W }, uNarrow: { value: 7 / 604 * W } },
      { transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
  core.position.z = ring.mark_depth / 2 + 0.002;
  core.renderOrder = 3;
  pivot.add(markMesh, core);

  // ---- Stage labels (3D, facing the camera) ----
  const scale = 4;                                       // canvas pixels per landing px
  const canvas = document.createElement('canvas');
  const cellH = 24 * scale;
  canvas.width = 1024; canvas.height = cellH * stages.length;
  const g2d = canvas.getContext('2d');
  await document.fonts?.ready;
  g2d.font = `400 ${CONFIG.labelPx * scale}px "Geist Mono", ui-monospace, Menlo, monospace`;
  if ('letterSpacing' in g2d) g2d.letterSpacing = `${CONFIG.labelSpacing * CONFIG.labelPx * scale}px`;
  g2d.textBaseline = 'middle';
  g2d.fillStyle = '#fff';
  const labelCells = new Float32Array(stages.length * 4), labelOn = new Float32Array(stages.length);
  const labelSize = stages.map((s, i) => {
    const text = s.label.toUpperCase(), w = Math.ceil(g2d.measureText(text).width) + 2 * scale;
    g2d.fillText(text, scale, cellH * (i + 0.5));
    labelCells.set([0, 1 - (i + 1) / stages.length, w / canvas.width, 1 / stages.length], i * 4);
    return [w / scale * px, cellH / scale * px];
  });
  const labelTexture = own(new THREE.CanvasTexture(canvas));
  labelTexture.anisotropy = 4;
  const labelGeometry = own(new THREE.PlaneGeometry(1, 1));
  labelGeometry.setAttribute('aCell', new THREE.InstancedBufferAttribute(labelCells, 4));
  labelGeometry.setAttribute('aOn', new THREE.InstancedBufferAttribute(labelOn, 1));
  const labelMesh = new THREE.InstancedMesh(labelGeometry, own(new THREE.ShaderMaterial({
    uniforms: { uGrey: grey, uText: { value: labelTexture } }, vertexShader: LABEL_VERTEX, fragmentShader: LABEL_FRAGMENT,
    transparent: true, depthWrite: false })), stages.length);
  labelMesh.frustumCulled = false;
  labelMesh.renderOrder = 2;
  centre.add(labelMesh);

  // ---- The list's lines (3D), placed under the HTML rows as seen from the rest view ----
  const section = ctx.section;
  const rows = section ? [...section.querySelectorAll('.cycle-rows button')] : [];
  const title = section?.querySelector('.cycle-title');
  const progress = new THREE.Vector4();
  const lineMaterial = own(new THREE.ShaderMaterial({ uniforms: { uGrey: grey, uProgress: { value: progress } },
    vertexShader: LINE_VERTEX, fragmentShader: LINE_FRAGMENT }));
  const lines = new THREE.Mesh(own(new THREE.BufferGeometry()), lineMaterial);
  lines.frustumCulled = false;
  group.add(lines);
  const rest = new THREE.PerspectiveCamera();
  rest.position.fromArray(contract.rest.position);
  rest.quaternion.fromArray(contract.rest.quaternion);
  const restRay = new THREE.Raycaster(), plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0), hit = new THREE.Vector3();
  function atScreen(x, y, out) {             // CSS px in the section at rest -> point on the ring's plane
    restRay.setFromCamera(new THREE.Vector2(x / innerWidth * 2 - 1, 1 - y / innerHeight * 2), rest);
    return restRay.ray.intersectPlane(plane, out) ?? out.set(0, 0, 0);
  }
  function layoutLines() {
    if (!section || !title) return;
    rest.fov = camera.fov; rest.aspect = camera.aspect; rest.near = camera.near; rest.far = camera.far;
    rest.updateProjectionMatrix(); rest.updateMatrixWorld();
    const top = section.getBoundingClientRect().top;
    const a = new THREE.Vector3(), b = new THREE.Vector3();
    const thick = atScreen(0, 0, a).distanceTo(atScreen(0, 1, b));   // one CSS px on the plane
    const position = [], u = [], row = [], index = [];
    const add = (x0, x1, y, lane, z) => {
      atScreen(x0, y, a); atScreen(x1, y, b);
      const k = position.length / 3;
      for (const [p, du] of [[a, 0], [b, 1]]) {
        position.push(p.x, p.y - thick / 2, z, p.x, p.y + thick / 2, z);
        u.push(du, du); row.push(lane, lane);
      }
      index.push(k, k + 2, k + 3, k, k + 3, k + 1);
    };
    const t = title.getBoundingClientRect();
    add(t.left, t.left + (rows[0]?.getBoundingClientRect().width ?? t.width), t.top - top + 0.5, -1, 0);
    rows.forEach((button, i) => {
      const r = button.getBoundingClientRect(), y = r.bottom - top - 0.5;
      add(r.left, r.right, y, -1, 0);
      add(r.left, r.right, y, i, 0.001);
    });
    const geometry = lines.geometry;
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(position, 3));
    geometry.setAttribute('aU', new THREE.Float32BufferAttribute(u, 1));
    geometry.setAttribute('aRow', new THREE.Float32BufferAttribute(row, 1));
    geometry.setIndex(index);
    section.classList.add('lines-3d');                    // the HTML rows drop their own CSS lines
  }
  layoutLines();

  // ---- Current ----
  const C = CONFIG.current;
  const uniforms = {
    uTime: time, uScale: { value: 1 }, uActive: { value: 0 },
    uRadius: { value: C.radius }, uPush: { value: C.push }, uSwirl: { value: C.swirl },
    uTrail: { value: C.trail }, uSizeBoost: { value: C.sizeBoost }, uDrift: { value: 0 },
    uRayO: { value: new THREE.Vector3() }, uRayD: { value: new THREE.Vector3(0, 0, -1) },
    uTrailO: { value: new THREE.Vector3() }, uTrailD: { value: new THREE.Vector3(0, 0, -1) },
  };
  const current = createCurrent(contract.flow, flowBuffer, uniforms);
  current.points.renderOrder = 4;
  group.add(current.points);

  // ---- The HTML rows ----
  let cyc = 0, hold = false, shown = -1;
  const listeners = [];
  rows.forEach((row, i) => {
    const enter = () => { cyc = i; hold = true; ctx.invalidate?.(); };
    const leave = () => { hold = false; };
    for (const [type, fn] of [['pointerenter', enter], ['focus', enter], ['click', enter], ['pointerleave', leave], ['blur', leave]]) {
      row.addEventListener(type, fn);
      listeners.push([row, type, fn]);
    }
  });
  function showStage(st) {
    if (st === shown) return;
    shown = st;
    rows.forEach((row, i) => row.toggleAttribute('aria-current', i === st));
  }

  // ---- Per frame: the signal, the stage colours, the mark ----
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  let tT = THREE.MathUtils.degToRad(ring.signal_deg) / (Math.PI / 2) * CONFIG.stageMs;   // the poster's pose
  const state = new Float32Array(3), velocity = new Float32Array(3), goal = new Float32Array(3);
  const euler = new THREE.Euler(), raycaster = new THREE.Raycaster(), trailCaster = new THREE.Raycaster();
  const target = new THREE.Vector2(), fast = new THREE.Vector2(), slow = new THREE.Vector2();
  let frozen = true, aspect = 2;

  let spin = 0;
  const turned = (local, out) => out.set(local.x * Math.cos(spin) + local.z * Math.sin(spin), local.y,
                                          -local.x * Math.sin(spin) + local.z * Math.cos(spin));
  const glowScale = [new THREE.Vector3(stageGlowSize, stageGlowSize, 1), new THREE.Vector3(signalGlowSize, signalGlowSize, 1)];
  const local = new THREE.Vector3(), radial = new THREE.Vector3(), labelScale = new THREE.Vector3(1, 1, 1);
  function pose(dt) {
    const S = CONFIG.stageMs;
    if (!reduced) spin = (spin + dt * 2 * Math.PI / CONFIG.orbitSeconds) % (2 * Math.PI);
    orbit.rotation.y = spin;
    if (hold) { if (Math.floor(tT / S) % 4 !== cyc) tT = cyc * S; }
    else tT = (tT + Math.min(dt * 1000, 100)) % (S * 4);
    const st = Math.floor(tT / S) % 4, fr = (tT % S) / S;
    const e = reduced ? 0 : 0.55 * fr + 0.45 * (0.5 - 0.5 * Math.cos(Math.PI * fr));
    const deg = (st + e) * 90;
    signalAngle.value = THREE.MathUtils.degToRad(deg);
    onRing(deg, point);
    spheres.setMatrixAt(stages.length, matrix.compose(point, noTurn, new THREE.Vector3(0.5, 0.5, 0.5)));
    glows.setMatrixAt(stages.length, matrix.compose(turned(point, local).setZ(local.z - 0.008), noTurn, glowScale[1]));
    stages.forEach((s, i) => {               // glows and labels follow their spheres but face the camera
      onRing(s.deg, point);
      turned(point, local);
      glows.setMatrixAt(i, matrix.compose(radial.copy(local).setZ(local.z - 0.01), noTurn, glowScale[0]));
      turned(radial.set(Math.sin(THREE.MathUtils.degToRad(s.deg)), Math.cos(THREE.MathUtils.degToRad(s.deg)), 0), radial);
      local.addScaledVector(radial, CONFIG.labelOut * px);
      labelScale.set(labelSize[i][0], labelSize[i][1], 1);
      labelMesh.setMatrixAt(i, matrix.compose(local, noTurn, labelScale));
    });
    labelMesh.instanceMatrix.needsUpdate = true;
    if (!hold) cyc = st;
    showStage(st);
    const k = Math.min(1, dt / CONFIG.fadeSeconds);
    stages.forEach((s, i) => {
      s.on += ((i === st ? 1 : 0) - s.on) * (dt > 0 ? k : 1);
      for (let c = 0; c < 3; c++) {
        rim[i * 3 + c] = THREE.MathUtils.lerp(srgbToLinear(DIM_RIM[c]), s.linear[c], s.on);
        dot[i * 3 + c] = THREE.MathUtils.lerp(srgbToLinear(DIM_DOT[c]), s.linear[c], s.on);
      }
      glowData.set([...s.linear, 0.4 * s.on], i * 4);
      labelOn[i] = s.on;
      const goalLine = i === st ? 1 : 0, rate = dt > 0 ? Math.min(1, dt * CONFIG.underlineRate) : 1;
      progress.setComponent(i, progress.getComponent(i) + (goalLine - progress.getComponent(i)) * rate);
    });
    labelGeometry.attributes.aOn.needsUpdate = true;
    for (const name of ['aRim', 'aDot']) sphereGeometry.attributes[name].needsUpdate = true;
    glowGeometry.attributes.aGlow.needsUpdate = true;
    spheres.instanceMatrix.needsUpdate = true;
    glows.instanceMatrix.needsUpdate = true;
  }
  pose(0);

  return {
    group,
    counts: { stages: stages.length, flow: contract.flow.count },
    setFrozen(value) { frozen = value; },
    setGrey(value) { grey.value = value; },
    setVisible() {},
    resize({ width, height, pixelScale }) { aspect = width / height; uniforms.uScale.value = pixelScale; requestAnimationFrame(layoutLines); },
    update(dt) {
      if (frozen) return false;
      const { pointer } = ctx;
      time.value += dt;
      pose(dt);
      target.set(pointer.x, pointer.y);
      fast.lerp(target, 1 - Math.exp(-dt * 10));
      slow.lerp(target, 1 - Math.exp(-dt * 2.2));
      const presence = uniforms.uActive;
      presence.value += ((pointer.inside ? 1 : 0) - presence.value) * (1 - Math.exp(-dt * (pointer.inside ? 6 : 2)));
      raycaster.setFromCamera(fast, camera);
      trailCaster.setFromCamera(slow, camera);
      uniforms.uRayO.value.copy(raycaster.ray.origin); uniforms.uRayD.value.copy(raycaster.ray.direction);
      uniforms.uTrailO.value.copy(trailCaster.ray.origin); uniforms.uTrailD.value.copy(trailCaster.ray.direction);

      // the mark: the hero tile spring, toward a tilt that leans to the cursor and a small lift
      group.updateMatrixWorld(true);
      point.setFromMatrixPosition(centre.matrixWorld).project(camera);
      const { reach, tilt, lift, stiffness, damping } = CONFIG.mark;
      const dx = (fast.x - point.x) * aspect, dy = fast.y - point.y;
      const influence = Math.exp(-(dx * dx + dy * dy) / (reach * reach)) * presence.value;
      goal[0] = -dy / reach * tilt * influence + Math.sin(time.value * 0.5) * 0.012;
      goal[1] = dx / reach * tilt * influence + Math.sin(time.value * 0.37) * 0.012;
      goal[2] = lift * influence;
      for (let t = 0; t < dt; t += 1 / 120) {
        const h = Math.min(1 / 120, dt - t);
        for (let k = 0; k < 3; k++) {
          velocity[k] += (stiffness * (goal[k] - state[k]) - damping * velocity[k]) * h;
          state[k] += velocity[k] * h;
        }
      }
      pivot.rotation.copy(euler.set(state[0], state[1], 0));
      pivot.position.z = state[2];
      return true;
    },
    dispose() {
      for (const [row, type, fn] of listeners) row.removeEventListener(type, fn);
      section?.classList.remove('lines-3d');
      disposables.forEach(d => d.dispose());
      current.dispose();
    },
  };
}
