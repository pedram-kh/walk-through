// Stop 01, hero: the tile wall, particle current and videos from the Blender export
// (stop.glb, flow.bin, stop.json). The galaxy dust in dust.bin is not drawn: the current is
// the only particles at this stop (your request, 2026-10-05). Blender owns the layout;
// this module owns the motion. The route runtime owns the renderer, camera and scroll,
// and drives this stop through the stop interface (see PLAN.md).
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { GREY_GLSL, addGrey } from '../../runtime/materials.js';
import { createCurrent } from '../../runtime/flow.js';

const CONFIG = {
  // Real photos: tile label -> image URL (relative to this stop's folder).
  // Labels are listed in stop.json. Photo tiles without an image keep a flat placeholder;
  // galaxy tiles show their image in one colour (the tile's tint) under the stars.
  images: Object.fromEntries(['hero', 'portrait', 'texture', 'landscape', 'statement', 'card', 'product', 'splash',
    'ugc', 'far_left', 'behind_hero', 'top_violet', 'top_teal', 'right_blue', 'side_strip', 'mid_violet',
    'right_teal', 'floor_teal', 'floor_streak'].map(label => [label, `media/images/${label}.jpg`])),
  galaxyPhoto: 0.85,      // how strongly a galaxy tile's photo shows through (0 = stars only)
  // Small spaced captions that ride on a tile: tile label -> [text, corner, offset in tile units].
  // The caption's left edge sits at the corner plus the offset, centred vertically on it.
  tags: {
    product: ['UGC', 'top-left', [0, 0.14]],
    hero: ['Motion', 'top-left', [0, 0.18]],
    statement: ['Static', 'top-left', [0, 0.16]],
    texture: ['Design', 'bottom-left', [0, -0.16]],
    card: ['Hi-Fi', 'bottom-left', [0.12, 0.16]],
  },
  // Video tiles: label -> clip. The poster shows first (in place of the image), then the
  // video takes over once it can play. Videos only play while this stop is live.
  videos: Object.fromEntries(['hero', 'portrait', 'product'].map(label =>
    [label, { src: `media/videos/${label}.mp4`, poster: `media/videos/${label}-poster.jpg` }])),
  tile: { reach: 0.55, tilt: 0.32, lift: 0.3, stiffness: 55, damping: 11 },
  current: { radius: 1.25, push: 0.6, swirl: 0.45, trail: 0.35, sizeBoost: 1.9, drift: 0.035 },
  parallax: 0.045,
};

const GALAXY_FRAGMENT = /* glsl */`
uniform vec3 uTint; uniform vec3 uBright; uniform vec2 uSize; uniform vec2 uPointer; uniform float uTime;
uniform sampler2D uPhoto; uniform float uPhotoMix;
varying vec2 vUv;
${GREY_GLSL}
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
  vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}
void main() {
  vec2 p = vUv * uSize;
  float cloud = noise(p * 1.3 + 7.0) * 0.6 + noise(p * 3.4 + uTime * 0.03) * 0.4;
  vec3 col = mix(uTint * 0.05, uTint * 0.5, smoothstep(0.25, 0.85, cloud));
  if (uPhotoMix > 0.0) {                     // one-colour photo: shadows -> deep tint, highlights -> bright tint
    float l = sqrt(dot(texture2D(uPhoto, vUv).rgb, vec3(0.2126, 0.7152, 0.0722)));
    vec3 duo = mix(uTint * 0.03, mix(uTint * 0.55, uBright * 0.8, l), smoothstep(0.05, 0.75, l));
    col = mix(col, duo * (0.85 + 0.3 * cloud), uPhotoMix);
  }
  vec2 g = p * 26.0, id = floor(g), f = fract(g) - 0.5;
  float h = hash(id);
  vec2 o = (vec2(hash(id + 3.1), hash(id + 7.7)) - 0.5) * 0.6;
  float twinkle = 0.6 + 0.4 * sin(uTime * (0.6 + h * 1.8) + h * 40.0);
  float star = smoothstep(0.17, 0.0, length(f - o)) * step(0.45, h) * twinkle;
  vec2 d = p - uPointer;
  float glow = exp(-dot(d, d) / 0.45);
  col += uBright * star * (0.9 + 2.2 * glow) + uTint * glow * 0.22;
  gl_FragColor = vec4(toGrey(col), 1.0);
  #include <colorspace_fragment>
}`;
// ctx (from the runtime): dir, camera, overlay (element for HTML captions), pointer
// ({ x, y } in normalised device coordinates, inside), invalidate() to request a render.
export async function load(ctx) {
  const at = path => ctx.dir + path;
  const cleanup = [], clips = [];
  let disposed = false, frozen = true, visible = true;
  const listen = (target, type, fn, options) => {
    target.addEventListener(type, fn, options);
    cleanup.push(() => target.removeEventListener(type, fn, options));
  };
  const fetchAs = async (url, kind) => {
    const response = await fetch(url);
    if (!response.ok) throw Error('Missing stop 01 asset: ' + url);
    return response[kind]();
  };
  const [contract, gltf, flowBuffer] = await Promise.all([
    fetchAs(at('stop.json'), 'json'), new GLTFLoader().loadAsync(at('stop.glb')), fetchAs(at('flow.bin'), 'arrayBuffer'),
  ]);
  const palette = Object.fromEntries(Object.entries(contract.palette_linear).map(([k, v]) => [k, new THREE.Color().setRGB(...v)]));
  const { camera } = ctx;
  const group = new THREE.Group(), root = new THREE.Group();
  group.add(root);
  const grey = { value: 0 };

  // ---- Tiles: one pivot per tile at its rest transform -----------------------
  gltf.scene.updateMatrixWorld(true);
  const time = { value: 0 };
  const loader = new THREE.TextureLoader();
  const setMap = (material, texture) => {
    texture.flipY = false; texture.colorSpace = THREE.SRGBColorSpace;
    material.map?.dispose();
    material.map = texture; material.color.set(0xffffff); material.needsUpdate = true;
    ctx.invalidate();
  };
  function loadClip({ src }, material) {
    const video = document.createElement('video');
    Object.assign(video, { muted: true, defaultMuted: true, loop: true, playsInline: true, preload: 'auto' });
    const clip = { video, texture: null };
    listen(video, 'canplay', () => {
      if (clip.texture || disposed) return;
      clip.texture = new THREE.VideoTexture(video);
      clip.texture.needsUpdate = true;   // upload the current frame now; a paused video sends no new ones
      setMap(material, clip.texture);
    });
    listen(video, 'error', () => console.warn('Stop 01 video failed to load, keeping its poster:', src), { once: true });
    video.src = at(src);
    clips.push(clip);
  }
  const tiles = contract.tiles.map((info, index) => {
    const source = gltf.scene.getObjectByName(info.name);
    if (!source?.isMesh) throw Error('Tile missing from stop.glb: ' + info.name);
    const restPosition = new THREE.Vector3(), restQuaternion = new THREE.Quaternion(), scale = new THREE.Vector3();
    source.matrixWorld.decompose(restPosition, restQuaternion, scale);
    let material;
    if (info.kind === 'galaxy') {
      material = new THREE.ShaderMaterial({
        uniforms: {
          uTint: { value: palette[info.look] }, uBright: { value: palette[info.look + '_bright'] },
          uSize: { value: new THREE.Vector2(info.width, info.height) },
          uPointer: { value: new THREE.Vector2(-99, -99) }, uTime: time,
          uPhoto: { value: null }, uPhotoMix: { value: 0 }, uGrey: grey,
        },
        vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
        fragmentShader: GALAXY_FRAGMENT, side: THREE.DoubleSide,
      });
      const url = CONFIG.images[info.label];
      if (url) loader.load(at(url), texture => {
        if (disposed) { texture.dispose(); return; }
        texture.flipY = false; texture.colorSpace = THREE.SRGBColorSpace;
        material.uniforms.uPhoto.value = texture; material.uniforms.uPhotoMix.value = CONFIG.galaxyPhoto;
        ctx.invalidate();
      });
    } else {
      const color = typeof info.look === 'string'
        ? palette[info.look].clone().multiplyScalar(0.5)
        : new THREE.Color().setRGB(info.look * 0.45, info.look * 0.45, info.look * 0.45);
      material = addGrey(new THREE.MeshBasicMaterial({ color, side: THREE.DoubleSide }), grey);
      const clip = CONFIG.videos[info.label];
      const url = clip?.poster ?? CONFIG.images[info.label];
      if (url) loader.load(at(url), texture => {
        if (disposed || material.map?.isVideoTexture) texture.dispose();   // the video got there first
        else setMap(material, texture);
      });
      if (clip) loadClip(clip, material);
    }
    let tag = null, tagAnchor = null;
    if (CONFIG.tags[info.label]) {
      const [text, corner, [dx, dy]] = CONFIG.tags[info.label];
      tagAnchor = new THREE.Vector3(info.width / 2 * (corner.endsWith('left') ? -1 : 1) + dx,
                                    info.height / 2 * (corner.startsWith('top') ? 1 : -1) + dy, 0);
      tag = Object.assign(document.createElement('span'), { className: 'tile-tag', textContent: text });
      tag.setAttribute('aria-hidden', 'true');
      ctx.overlay.append(tag);
      cleanup.push(() => tag.remove());
    }
    const pivot = new THREE.Group();
    pivot.position.copy(restPosition);
    pivot.quaternion.copy(restQuaternion);
    pivot.add(new THREE.Mesh(source.geometry, material));
    root.add(pivot);
    return {
      info, pivot, material, restPosition, restQuaternion, tag, tagAnchor,
      normal: new THREE.Vector3(0, 0, 1).applyQuaternion(restQuaternion),
      screen: new THREE.Vector2(), phase: index * 1.7,
    };
  });
  root.updateMatrixWorld(true);

  // ---- Cursor and time uniforms for the current -------------------------------
  const pointerUniforms = {
    uTime: time, uScale: { value: 1 }, uActive: { value: 0 },
    uRadius: { value: CONFIG.current.radius }, uPush: { value: CONFIG.current.push }, uSwirl: { value: CONFIG.current.swirl },
    uTrail: { value: CONFIG.current.trail }, uSizeBoost: { value: CONFIG.current.sizeBoost }, uDrift: { value: CONFIG.current.drift },
    uRayO: { value: new THREE.Vector3() }, uRayD: { value: new THREE.Vector3(0, 0, -1) },
    uTrailO: { value: new THREE.Vector3() }, uTrailD: { value: new THREE.Vector3(0, 0, -1) },
  };
  const point = new THREE.Vector3(), inverse = new THREE.Matrix4();

  // ---- Current: particles flowing along the paths in stop.json ------------------
  const current = createCurrent(contract.flow, flowBuffer, pointerUniforms);
  root.add(current.points);
  cleanup.push(() => current.dispose());

  // ---- Captions follow their tiles on screen ---------------------------------
  let aspect = 2, stageW = 0, stageH = 0;
  const tagPoint = new THREE.Vector3();
  function placeTags() {
    if (!visible) return;
    group.updateMatrixWorld(true);
    for (const tile of tiles) {
      if (!tile.tag) continue;
      tagPoint.copy(tile.tagAnchor).applyMatrix4(tile.pivot.matrixWorld).project(camera);
      const onScreen = tagPoint.z < 1 && Math.abs(tagPoint.x) < 1.2 && Math.abs(tagPoint.y) < 1.2;
      tile.tag.style.visibility = onScreen ? '' : 'hidden';
      tile.tag.style.transform = `translate(${((tagPoint.x + 1) / 2 * stageW).toFixed(1)}px, ${((1 - tagPoint.y) / 2 * stageH).toFixed(1)}px) translateY(-50%)`;
    }
  }

  // ---- Animation: bounded springs on tilt and lift ---------------------------
  const count = tiles.length;
  const state = new Float32Array(count * 3), velocity = new Float32Array(count * 3), goal = new Float32Array(count * 3);
  const raycaster = new THREE.Raycaster(), trailCaster = new THREE.Raycaster();
  const localRay = new THREE.Ray(), tilt = new THREE.Quaternion(), euler = new THREE.Euler();
  const target = new THREE.Vector2(), fast = new THREE.Vector2(), slow = new THREE.Vector2();

  function animate(dt) {
    const { pointer } = ctx;
    target.set(pointer.x, pointer.y);
    time.value += dt;
    fast.lerp(target, 1 - Math.exp(-dt * 10));
    slow.lerp(target, 1 - Math.exp(-dt * 2.2));
    const presence = pointerUniforms.uActive;
    presence.value += ((pointer.inside ? 1 : 0) - presence.value) * (1 - Math.exp(-dt * (pointer.inside ? 6 : 2)));

    root.rotation.set(-fast.y * CONFIG.parallax * presence.value, fast.x * CONFIG.parallax * presence.value, 0);
    group.updateMatrixWorld(true);
    raycaster.setFromCamera(fast, camera);
    trailCaster.setFromCamera(slow, camera);
    pointerUniforms.uRayO.value.copy(raycaster.ray.origin); pointerUniforms.uRayD.value.copy(raycaster.ray.direction);
    pointerUniforms.uTrailO.value.copy(trailCaster.ray.origin); pointerUniforms.uTrailD.value.copy(trailCaster.ray.direction);

    const { reach, tilt: tiltAmount, lift, stiffness, damping } = CONFIG.tile;
    for (let i = 0; i < count; i++) {
      const tile = tiles[i], k = i * 3;
      point.copy(tile.restPosition).applyMatrix4(group.matrixWorld).project(camera);
      tile.screen.set(point.x, point.y);
      const dx = (fast.x - tile.screen.x) * aspect * 0.85, dy = fast.y - tile.screen.y;   // 0.85 = 2.2 / the original 2.59 frame
      const influence = Math.exp(-(dx * dx + dy * dy) / (reach * reach)) * presence.value;
      goal[k] = -dy / reach * tiltAmount * influence + Math.sin(time.value * 0.5 + tile.phase) * 0.012;
      goal[k + 1] = dx / reach * tiltAmount * influence + Math.sin(time.value * 0.37 + tile.phase * 1.3) * 0.012;
      goal[k + 2] = lift * influence;
    }
    for (let t = 0; t < dt; t += 1 / 120) {
      const h = Math.min(1 / 120, dt - t);
      for (let k = 0; k < state.length; k++) {
        velocity[k] += (stiffness * (goal[k] - state[k]) - damping * velocity[k]) * h;
        state[k] += velocity[k] * h;
      }
    }
    for (let i = 0; i < count; i++) {
      const tile = tiles[i], k = i * 3;
      tile.pivot.quaternion.copy(tile.restQuaternion).multiply(tilt.setFromEuler(euler.set(state[k], state[k + 1], 0)));
      tile.pivot.position.copy(tile.restPosition).addScaledVector(tile.normal, state[k + 2]);
      tile.pivot.position.y += Math.sin(time.value * 0.4 + tile.phase) * 0.02;
      if (tile.info.kind === 'galaxy') {       // where the cursor meets this tile, in tile units
        tile.pivot.updateMatrixWorld(true);
        localRay.copy(raycaster.ray).applyMatrix4(inverse.copy(tile.pivot.matrixWorld).invert());
        const s = -localRay.origin.z / localRay.direction.z;
        tile.material.uniforms.uPointer.value.set(
          pointer.inside ? localRay.origin.x + localRay.direction.x * s + tile.info.width / 2 : -99,
          pointer.inside ? localRay.origin.y + localRay.direction.y * s + tile.info.height / 2 : -99);
      }
    }
  }

  return {
    group,
    counts: { tiles: count, flow: contract.flow.count, videos: clips.length },
    // Frozen: the clock stops and videos pause; the scene keeps its last pose.
    setFrozen(value) {
      if (disposed || value === frozen) return;
      frozen = value;
      for (const { video } of clips) {
        if (frozen) video.pause();
        else video.play().catch(() => {});   // a failed clip already warned and keeps its poster
      }
    },
    setGrey(value) { grey.value = value; },
    setVisible(value) {
      visible = value;
      for (const tile of tiles) if (tile.tag) tile.tag.style.display = value ? '' : 'none';
    },
    resize({ width, height, pixelScale }) {
      stageW = width; stageH = height; aspect = width / height;
      pointerUniforms.uScale.value = pixelScale;
    },
    // Called every rendered frame while visible. Returns true while it animates.
    update(dt) {
      if (!frozen) animate(dt);
      placeTags();
      return !frozen;
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      cleanup.forEach(fn => fn());
      for (const { video, texture } of clips) { video.pause(); video.removeAttribute('src'); video.load(); texture?.dispose(); }
      group.traverse(o => { o.geometry?.dispose(); o.material?.map?.dispose(); o.material?.uniforms?.uPhoto?.value?.dispose(); o.material?.dispose(); });
    },
  };
}
