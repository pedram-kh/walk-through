// Stop 03, the problem ("AI moves fast"): three rows of photo cards that drift sideways
// forever like the landing HTML (rows 1 and 3 right, row 2 left), upright and turned in a
// checkerboard zigzag. Cards fade out at the row ends and wrap round off screen; cards near
// the cursor tilt and lift like the hero tiles. Behind each row, the landing's motion trail.
// One draw call for all cards (instanced, faces from cards.jpg), one for the trails.
import * as THREE from 'three';
import { GREY_GLSL } from '../../runtime/materials.js';
import { createCurrent } from '../../runtime/flow.js';

const CONFIG = {
  current: { radius: 1.25, push: 0.6, swirl: 0.45, trail: 0.35, sizeBoost: 1.9 },   // as at stop 01
  tile: { reach: 0.55, tilt: 0.32, lift: 0.3, stiffness: 55, damping: 11 },        // hero tile hover
  fade: { outside: 0.2, inside: 0.12 },    // row-end fade, in card widths outside / inside the row's ends
  trail: { height: 0.73, behind: 0.35 },   // landing MotionTrail: middle 56% of a 239 px row; depth behind the cards
};

const CARD_VERTEX = /* glsl */`
attribute vec4 aCell;            // atlas rectangle: u, v, width, height
varying vec2 vUv;
varying float vX;                // along the row, for the row-end fade (per pixel)
void main() {
  vec4 local = instanceMatrix * vec4(position, 1.0);
  vUv = aCell.xy + uv * aCell.zw;
  vX = local.x;
  gl_Position = projectionMatrix * modelViewMatrix * local;
}`;

const CARD_FRAGMENT = /* glsl */`
uniform sampler2D uAtlas;
uniform float uLeft, uRight, uOutside, uInside;
varying vec2 vUv;
varying float vX;
${GREY_GLSL}
void main() {
  float fade = smoothstep(uLeft - uOutside, uLeft + uInside, vX) * (1.0 - smoothstep(uRight - uInside, uRight + uOutside, vX));
  if (fade < 0.004) discard;
  gl_FragColor = vec4(toGrey(texture2D(uAtlas, vUv).rgb), fade);
  #include <colorspace_fragment>
}`;

// Landing: repeating-linear-gradient(180deg, white 3% 0-1px, transparent 1-7px) over a horizontal
// violet-to-blue gradient (mirrored for the row that drifts left), faded at top and bottom.
const TRAIL_VERTEX = /* glsl */`
attribute float aDir;
varying vec2 vUv;
varying float vDir;
void main() { vUv = uv; vDir = aDir; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;

const TRAIL_FRAGMENT = /* glsl */`
uniform float uLines;
varying vec2 vUv;
varying float vDir;
${GREY_GLSL}
vec4 stop(float x, float a, float b, vec4 ca, vec4 cb) { return mix(ca, cb, clamp((x - a) / (b - a), 0.0, 1.0)); }
void main() {
  float x = vDir > 0.0 ? vUv.x : 1.0 - vUv.x;
  vec4 none = vec4(0.0), violet = vec4(0.482, 0.251, 0.6, 0.16), blue = vec4(0.329, 0.506, 0.663, 0.07);
  vec4 c = vDir > 0.0
    ? (x < 0.24 ? stop(x, 0.12, 0.24, none, violet) : x < 0.52 ? stop(x, 0.24, 0.52, violet, blue) : stop(x, 0.52, 0.78, blue, none))
    : (x < 0.10 ? stop(x, 0.02, 0.10, none, violet) : x < 0.40 ? stop(x, 0.10, 0.40, violet, blue) : stop(x, 0.40, 0.70, blue, none));
  float line = step(fract(vUv.y * uLines), 1.0 / 7.0) * 0.03;
  float mask = smoothstep(0.0, 0.35, vUv.y) * smoothstep(1.0, 0.65, vUv.y);
  vec3 srgb = c.rgb * c.a + vec3(line);          // over black, as the page composites it
  gl_FragColor = vec4(toGrey(pow(srgb, vec3(2.2))) * mask, 1.0);
  #include <colorspace_fragment>
}`;

export async function load(ctx) {
  const fetchAs = async (file, kind) => {
    const response = await fetch(ctx.dir + file);
    if (!response.ok) throw Error('Missing stop 03 asset: ' + file);
    return response[kind]();
  };
  const contract = await fetchAs('stop.json', 'json');
  const [atlas, flowBuffer] = await Promise.all([
    new THREE.TextureLoader().loadAsync(ctx.dir + contract.card.atlas), fetchAs('flow.bin', 'arrayBuffer'),
  ]);
  atlas.colorSpace = THREE.SRGBColorSpace;
  atlas.anisotropy = 4;
  const { camera } = ctx;
  const group = new THREE.Group();
  const grey = { value: 0 }, time = { value: 0 };
  const { width: cardW, height: cardH, zigzag_deg: zigzag } = contract.card;
  const rows = contract.rows, loop = rows[0].loop;

  // ---- Cards: one instance per card; the drift and the hover move the instances ----
  const cards = contract.cards.map((card, i) => ({
    ...card, slot: i, sign: Math.sign(card.turn_deg), phase: i * 1.7,
    rest: new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), THREE.MathUtils.degToRad(card.turn_deg)),
  }));
  const cell = new Float32Array(cards.length * 4);
  cards.forEach((card, i) => cell.set(card.uv, i * 4));
  const geometry = new THREE.PlaneGeometry(cardW, cardH);
  geometry.setAttribute('aCell', new THREE.InstancedBufferAttribute(cell, 4));
  const cardMaterial = new THREE.ShaderMaterial({
    uniforms: {
      uAtlas: { value: atlas }, uGrey: grey,
      uLeft: { value: rows[0].left }, uRight: { value: rows[0].right },
      uOutside: { value: CONFIG.fade.outside * cardW }, uInside: { value: CONFIG.fade.inside * cardW },
    },
    vertexShader: CARD_VERTEX, fragmentShader: CARD_FRAGMENT, transparent: true, side: THREE.DoubleSide,
  });
  const mesh = new THREE.InstancedMesh(geometry, cardMaterial, cards.length);
  mesh.frustumCulled = false;
  group.add(mesh);

  // ---- Motion trails behind the rows ----
  const trailPositions = [], trailUv = [], trailDir = [], trailIndex = [];
  rows.forEach((row, r) => {
    const x0 = row.left - cardW * 0.5, x1 = row.right + cardW * 0.25;
    const [, y, z] = row.centre, h = cardH * CONFIG.trail.height / 2, back = z - CONFIG.trail.behind;
    trailPositions.push(x0, y - h, back, x1, y - h, back, x1, y + h, back, x0, y + h, back);
    trailUv.push(0, 0, 1, 0, 1, 1, 0, 1);
    const dir = Math.sign(row.speed_cards_per_s);
    trailDir.push(dir, dir, dir, dir);
    trailIndex.push(r * 4, r * 4 + 1, r * 4 + 2, r * 4, r * 4 + 2, r * 4 + 3);
  });
  const trailGeometry = new THREE.BufferGeometry();
  trailGeometry.setAttribute('position', new THREE.Float32BufferAttribute(trailPositions, 3));
  trailGeometry.setAttribute('uv', new THREE.Float32BufferAttribute(trailUv, 2));
  trailGeometry.setAttribute('aDir', new THREE.Float32BufferAttribute(trailDir, 1));
  trailGeometry.setIndex(trailIndex);
  const trailMaterial = new THREE.ShaderMaterial({
    uniforms: { uGrey: grey, uLines: { value: 239 * CONFIG.trail.height / 7 } },   // one line per 7 landing px
    vertexShader: TRAIL_VERTEX, fragmentShader: TRAIL_FRAGMENT,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
  });
  const trails = new THREE.Mesh(trailGeometry, trailMaterial);
  trails.renderOrder = -1;
  group.add(trails);

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
  current.points.renderOrder = 1;
  group.add(current.points);

  // ---- Placement: drift along the row, wrapped off the row's ends; hover tilt and lift ----
  const drift = rows.map(() => 0);                          // in pitches
  const count = cards.length;
  const state = new Float32Array(count * 3), velocity = new Float32Array(count * 3), goal = new Float32Array(count * 3);
  const centre = new THREE.Vector3(), quaternion = new THREE.Quaternion(), tilt = new THREE.Quaternion();
  const euler = new THREE.Euler(), unit = new THREE.Vector3(1, 1, 1), matrix = new THREE.Matrix4(), point = new THREE.Vector3();
  const wrap = v => ((v + 1) % loop + loop) % loop - 1;      // into [-1, loop - 1)

  function cardCentre(card, out) {
    const row = rows[card.row];
    return out.set(row.left + cardW / 2 + wrap(card.index + drift[card.row]) * row.pitch, row.centre[1], row.centre[2]);
  }
  function place() {
    for (let i = 0; i < count; i++) {
      const card = cards[i], k = i * 3;
      cardCentre(card, centre);
      centre.z += state[k + 2];
      quaternion.copy(card.rest).multiply(tilt.setFromEuler(euler.set(state[k], state[k + 1], 0)));
      mesh.setMatrixAt(i, matrix.compose(centre, quaternion, unit));
    }
    mesh.instanceMatrix.needsUpdate = true;
  }
  place();

  const raycaster = new THREE.Raycaster(), trailCaster = new THREE.Raycaster();
  const target = new THREE.Vector2(), fast = new THREE.Vector2(), slow = new THREE.Vector2();
  let frozen = true, aspect = 2;
  return {
    group,
    counts: { cards: count, flow: contract.flow.count },
    setFrozen(value) { frozen = value; },
    setGrey(value) { grey.value = value; },
    setVisible() {},
    resize({ width, height, pixelScale }) { aspect = width / height; uniforms.uScale.value = pixelScale; },
    update(dt) {
      if (frozen) return false;
      const { pointer } = ctx;
      time.value += dt;
      rows.forEach((row, r) => { drift[r] = (drift[r] + row.speed_cards_per_s * dt) % loop; });
      target.set(pointer.x, pointer.y);
      fast.lerp(target, 1 - Math.exp(-dt * 10));
      slow.lerp(target, 1 - Math.exp(-dt * 2.2));
      const presence = uniforms.uActive;
      presence.value += ((pointer.inside ? 1 : 0) - presence.value) * (1 - Math.exp(-dt * (pointer.inside ? 6 : 2)));
      raycaster.setFromCamera(fast, camera);
      trailCaster.setFromCamera(slow, camera);
      uniforms.uRayO.value.copy(raycaster.ray.origin); uniforms.uRayD.value.copy(raycaster.ray.direction);
      uniforms.uTrailO.value.copy(trailCaster.ray.origin); uniforms.uTrailD.value.copy(trailCaster.ray.direction);

      group.updateMatrixWorld(true);
      const { reach, tilt: tiltAmount, lift, stiffness, damping } = CONFIG.tile;
      for (let i = 0; i < count; i++) {
        const k = i * 3;
        point.copy(cardCentre(cards[i], centre)).applyMatrix4(group.matrixWorld).project(camera);
        const dx = (fast.x - point.x) * aspect, dy = fast.y - point.y;
        const influence = Math.exp(-(dx * dx + dy * dy) / (reach * reach)) * presence.value;
        goal[k] = -dy / reach * tiltAmount * influence + Math.sin(time.value * 0.5 + cards[i].phase) * 0.012;
        goal[k + 1] = dx / reach * tiltAmount * influence + Math.sin(time.value * 0.37 + cards[i].phase * 1.3) * 0.012;
        goal[k + 2] = lift * influence;
      }
      for (let t = 0; t < dt; t += 1 / 120) {
        const h = Math.min(1 / 120, dt - t);
        for (let k = 0; k < state.length; k++) {
          velocity[k] += (stiffness * (goal[k] - state[k]) - damping * velocity[k]) * h;
          state[k] += velocity[k] * h;
        }
      }
      place();
      return true;
    },
    dispose() {
      geometry.dispose(); cardMaterial.dispose(); atlas.dispose();
      trailGeometry.dispose(); trailMaterial.dispose();
      current.dispose();
    },
  };
}
