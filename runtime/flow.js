// Particle currents, shared by stops (the current that wraps a stop's objects) and the
// runtime (journey currents between stops). Particles sit on fibres at a fixed offset
// from a path and move along it. Data comes from Blender (tools/flow_common.py):
// paths as points, normals and binormals, and 11 floats per particle in a .bin file.
import * as THREE from 'three';

// Shared by dust and currents: the cursor ray (and its slower trail) push points aside.
export const POINTER_PUSH = /* glsl */`
uniform float uTime, uScale, uActive, uRadius, uPush, uSwirl, uTrail, uSizeBoost, uDrift;
uniform vec3 uRayO, uRayD, uTrailO, uTrailD;
varying vec3 vColor;
vec4 pushFrom(vec3 p, vec3 o, vec3 d) {      // xyz = offset, w = influence
  vec3 away = p - (o + d * dot(p - o, d));
  float dist = max(length(away), 1e-4);
  float f = exp(-dist * dist / (uRadius * uRadius));
  vec3 n = away / dist;
  return vec4((n * uPush + cross(d, n) * uSwirl) * f, f);
}`;

export const POINT_FRAGMENT = /* glsl */`
varying vec3 vColor;
void main() {
  float a = smoothstep(0.5, 0.12, length(gl_PointCoord - 0.5));
  gl_FragColor = vec4(vColor * a, 1.0);
  #include <colorspace_fragment>
}`;

// Dust: points that drift and twinkle; aColor, aSize, aSeed per point.
export const DUST_VERTEX = /* glsl */`
attribute vec3 aColor; attribute float aSize; attribute float aSeed;
${POINTER_PUSH}
void main() {
  vec4 world = modelMatrix * vec4(position, 1.0);
  world.xyz += vec3(sin(uTime * 0.35 + aSeed * 40.0), cos(uTime * 0.28 + aSeed * 71.0), sin(uTime * 0.22 + aSeed * 13.0)) * uDrift;
  vec4 near = pushFrom(world.xyz, uRayO, uRayD);
  vec4 trail = pushFrom(world.xyz, uTrailO, uTrailD);
  world.xyz += (near.xyz + trail.xyz * uTrail) * uActive * (0.6 + aSeed * 0.8);
  vec4 view = viewMatrix * world;
  gl_Position = projectionMatrix * view;
  gl_PointSize = max(1.6, aSize * 2.0 * uSizeBoost * uScale / -view.z);
  float twinkle = 0.72 + 0.28 * sin(uTime * (0.8 + aSeed * 2.0) + aSeed * 50.0);
  vColor = aColor * twinkle * (1.0 + near.w * uActive * 1.4);
}`;

// Paths arrive as a texture: per path, rows of points, normals, binormals.
const FLOW_VERTEX = /* glsl */`
attribute vec3 aColor; attribute float aSize; attribute float aSeed;
attribute float aPath, aT, aRadius, aAngle, aRate; attribute vec2 aJitter;
uniform sampler2D uPath; uniform float uSamples, uTwist;
${POINTER_PUSH}
vec3 along(int row, float t) {               // linear between the two nearest samples
  float f = t * (uSamples - 1.0);
  int i = int(f), last = int(uSamples) - 1;
  return mix(texelFetch(uPath, ivec2(i, row), 0).xyz, texelFetch(uPath, ivec2(min(i + 1, last), row), 0).xyz, fract(f));
}
void main() {
  float t = fract(aT + uTime * aRate);
  int row = int(aPath + 0.5) * 3;
  vec3 n = normalize(along(row + 1, t)), b = normalize(along(row + 2, t));
  float angle = aAngle + uTwist * t + uTime * 0.12, taper = 0.35 + 0.65 * sin(3.14159265 * t);
  vec3 p = along(row, t) + (n * cos(angle) + b * sin(angle)) * aRadius * taper + n * aJitter.x + b * aJitter.y;
  vec4 world = modelMatrix * vec4(p, 1.0);
  vec4 near = pushFrom(world.xyz, uRayO, uRayD);
  vec4 trail = pushFrom(world.xyz, uTrailO, uTrailD);
  world.xyz += (near.xyz + trail.xyz * uTrail) * uActive * (0.6 + aSeed * 0.8);
  vec4 view = viewMatrix * world;
  gl_Position = projectionMatrix * view;
  gl_PointSize = max(1.2, aSize * 2.0 * uSizeBoost * uScale / -view.z);
  float fade = smoothstep(0.0, 0.06, t) * smoothstep(1.0, 0.9, t);   // hides the jump from end to start
  float twinkle = 0.75 + 0.25 * sin(uTime * (0.8 + aSeed * 2.0) + aSeed * 50.0);
  vColor = aColor * fade * twinkle * (1.0 + near.w * uActive * 1.4);
}`;

// Share of each current's particles that is drawn (every stop and journey). 0.6 = 40% less
// dense than built (your request, 2026-10-05). The kept particles are a fixed, even sample.
export const CURRENT_DENSITY = 0.6;

// Uniforms for a current that no cursor touches (journey currents).
export function stillPointerUniforms(time, sizeBoost = 1.9) {
  return {
    uTime: time, uScale: { value: 1 }, uActive: { value: 0 },
    uRadius: { value: 1 }, uPush: { value: 0 }, uSwirl: { value: 0 }, uTrail: { value: 0 },
    uSizeBoost: { value: sizeBoost }, uDrift: { value: 0 },
    uRayO: { value: new THREE.Vector3() }, uRayD: { value: new THREE.Vector3(0, 0, -1) },
    uTrailO: { value: new THREE.Vector3() }, uTrailD: { value: new THREE.Vector3(0, 0, -1) },
  };
}

// contract: { paths: [{ points, normals, binormals, length, speed }], samples, twist,
// count, floats_per_point }. uniforms: the pointer/time set (shared with dust if wanted).
// Returns { points, dispose }.
export function createCurrent(contract, buffer, uniforms) {
  const { paths, samples, twist, count: built, floats_per_point: fs } = contract;
  const flow = new Float32Array(buffer);
  if (flow.length !== built * fs) throw Error('Current data does not match its contract');
  const keep = [];
  for (let i = 0; i < built; i++) {
    const h = Math.abs(Math.sin(i * 12.9898) * 43758.5453) % 1;   // fixed per particle
    if (h < CURRENT_DENSITY) keep.push(i);
  }
  const count = keep.length;
  const pathData = new Float32Array(samples * paths.length * 3 * 4);
  paths.forEach((path, p) => ['points', 'normals', 'binormals'].forEach((key, k) =>
    path[key].forEach((v, i) => pathData.set(v, ((p * 3 + k) * samples + i) * 4))));
  const pathTexture = new THREE.DataTexture(pathData, samples, paths.length * 3, THREE.RGBAFormat, THREE.FloatType);
  pathTexture.needsUpdate = true;
  const column = width => new Float32Array(count * width);
  const [pathIndex, t0, radius, angle, rate, size, seed] = [1, 1, 1, 1, 1, 1, 1].map(column);
  const jitter = column(2), color = column(3);
  for (let i = 0; i < count; i++) {
    const k = keep[i] * fs, path = paths[flow[k]];
    pathIndex[i] = flow[k]; t0[i] = flow[k + 1]; radius[i] = flow[k + 2]; angle[i] = flow[k + 3];
    jitter.set([flow[k + 4], flow[k + 5]], i * 2);
    size[i] = flow[k + 6]; color.set([flow[k + 7], flow[k + 8], flow[k + 9]], i * 3); seed[i] = flow[k + 10];
    rate[i] = path.speed / path.length;   // path lengths per second
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(column(3), 3));   // placed in the shader
  for (const [name, array, width] of [['aPath', pathIndex, 1], ['aT', t0, 1], ['aRadius', radius, 1], ['aAngle', angle, 1],
    ['aRate', rate, 1], ['aJitter', jitter, 2], ['aSize', size, 1], ['aColor', color, 3], ['aSeed', seed, 1]]) {
    geometry.setAttribute(name, new THREE.BufferAttribute(array, width));
  }
  const material = new THREE.ShaderMaterial({
    uniforms: { ...uniforms, uPath: { value: pathTexture }, uSamples: { value: samples }, uTwist: { value: twist } },
    vertexShader: FLOW_VERTEX, fragmentShader: POINT_FRAGMENT,
    blending: THREE.AdditiveBlending, depthWrite: false, transparent: true,
  });
  const points = new THREE.Points(geometry, material);
  points.frustumCulled = false;
  return { points, dispose() { geometry.dispose(); material.dispose(); pathTexture.dispose(); } };
}
