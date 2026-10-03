// Route runtime: one renderer and camera for the whole walk-through. Scroll moves the
// camera along route.json; each stop is a module loaded from stops/<id>/stop.js.
// Only the stop at rest under the camera is live (animating, videos playing); every
// other visible stop is frozen and fades to black and white (PLAN.md, phases A-H).
import * as THREE from 'three';
import { Route } from './route.js';
import { StopLoader } from './loader.js';
import { mountDots } from './dots.js';
import { createCurrent, stillPointerUniforms } from './flow.js';

const MAX_PIXEL_RATIO = 1.5;
const GREY_SECONDS = 0.5;          // colour <-> black and white fade

export async function startRoute({ stage, overlay, isPaused, onFailure }) {
  const routeData = await fetch('route.json').then(r => { if (!r.ok) throw Error('Missing route.json'); return r.json(); });
  const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
  const canvas = renderer.domElement;
  canvas.setAttribute('aria-hidden', 'true');
  stage.append(canvas);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color().setRGB(0.00061, 0.00061, 0.00121);
  const camera = new THREE.PerspectiveCamera(30, 2, 0.1, 200);
  const halfH = Math.tan(THREE.MathUtils.degToRad(routeData.camera.horizontal_fov_deg) / 2);
  const route = new Route(routeData);
  const pointer = { x: 0, y: 0, inside: false };
  const cleanup = [];
  const listen = (target, type, fn, options) => {
    target.addEventListener(type, fn, options);
    cleanup.push(() => target.removeEventListener(type, fn, options));
  };
  let disposed = false, raf = 0, dirty = true, size = { width: 1, height: 1, pixelScale: 1 }, quality = MAX_PIXEL_RATIO;

  const loader = new StopLoader({
    route, scene, camera,
    makeContext: slot => ({ dir: slot.stop.dir, camera, overlay, pointer, invalidate: () => { dirty = true; } }),
    onLoaded: slot => {
      // A stop arrives frozen and in black and white, except the one already at rest on load.
      slot.grey = route.at(scrollY, { position: new THREE.Vector3(), quaternion: new THREE.Quaternion() }).rest === loader.slots.indexOf(slot) ? 0 : 1;
      slot.frozen = true;
      slot.module.setGrey(slot.grey);
      slot.module.resize(size);
      dirty = true;
    },
    onError: (slot, error) => {
      slot.error = error;
      console.warn(`Stop ${slot.stop.id} failed to load; showing its poster:`, error);
    },
  });
  const dots = mountDots(route);

  // Journey currents (one per segment): carry the particle current from stop to stop.
  // Shown while either of their stops is in view; flowing only while one of them is live.
  const journeys = routeData.segments.map((segment, k) => ({ k, data: segment.current, time: { value: 0 }, current: null }));
  async function loadJourneys() {
    for (const journey of journeys) {
      if (!journey.data || disposed) continue;
      try {
        const buffer = await fetch(journey.data.file).then(r => { if (!r.ok) throw Error('Missing ' + journey.data.file); return r.arrayBuffer(); });
        if (disposed) return;
        journey.uniforms = stillPointerUniforms(journey.time);
        journey.uniforms.uScale.value = size.pixelScale;
        journey.current = createCurrent(journey.data, buffer, journey.uniforms);
        journey.current.points.visible = false;
        scene.add(journey.current.points);
        dirty = true;
      } catch (error) { console.warn('Journey current failed to load:', error); }
    }
  }

  // ---- Sizing: keep the designed frame on any screen (as the hero always did) ----
  function resize() {
    const width = innerWidth, height = innerHeight;
    const aspect = width / height;
    const tanV = Math.max(halfH / aspect, halfH / routeData.camera.design_aspect);
    camera.fov = THREE.MathUtils.radToDeg(2 * Math.atan(tanV));
    camera.aspect = aspect;
    camera.updateProjectionMatrix();
    renderer.setPixelRatio(Math.min(devicePixelRatio, quality));
    renderer.setSize(width, height, false);
    size = { width, height, pixelScale: height * renderer.getPixelRatio() / (2 * tanV) };
    route.measure();
    for (const slot of loader.slots) slot.module?.resize(size);
    for (const journey of journeys) if (journey.uniforms) journey.uniforms.uScale.value = size.pixelScale;
    dirty = true;
  }
  const observer = new ResizeObserver(resize);
  observer.observe(document.body);
  cleanup.push(() => observer.disconnect());
  resize();

  listen(window, 'pointermove', e => {
    pointer.x = e.clientX / innerWidth * 2 - 1;
    pointer.y = 1 - e.clientY / innerHeight * 2;
    pointer.inside = true;
  }, { passive: true });
  listen(document.documentElement, 'pointerleave', () => { pointer.inside = false; });
  listen(window, 'scroll', () => { dirty = true; }, { passive: true });
  listen(canvas, 'webglcontextlost', e => { e.preventDefault(); fail(Error('Graphics context lost')); });

  // Stop 01 first: nothing is shown until it is ready.
  loader.focus(0);
  await loader.loading;
  if (loader.slots[0].status !== 'ready') { dispose(); throw loader.slots[0].error ?? Error('Stop 01 did not load'); }
  loadJourneys();       // in the background, after stop 01

  // ---- Frame loop ----------------------------------------------------------------
  const pose = { position: new THREE.Vector3(), quaternion: new THREE.Quaternion() };
  const lastPose = { position: new THREE.Vector3(1e9), quaternion: new THREE.Quaternion() };
  const diagnostics = { fps: 0, phase: '', stop: 0, live: -1, progress: 0, drawCalls: 0, triangles: 0, points: 0, pixelRatio: 0, loaded: [] };
  let last = performance.now(), streak = 0, streakTime = 0, slowFor = 0;

  function frame(now) {
    raf = requestAnimationFrame(frame);
    const wall = (now - last) / 1000, dt = Math.min(wall, 0.05);
    last = now;
    const state = route.at(scrollY, pose);
    dots.setCurrent(state.stop);
    loader.focus(state.stop);
    const paused = isPaused() || document.hidden;

    if (!pose.position.equals(lastPose.position) || !pose.quaternion.equals(lastPose.quaternion)) {
      camera.position.copy(pose.position);
      camera.quaternion.copy(pose.quaternion);
      camera.updateMatrixWorld();
      lastPose.position.copy(pose.position); lastPose.quaternion.copy(pose.quaternion);
      dirty = true;
    }

    let animating = false;
    for (const [i, slot] of loader.slots.entries()) {
      const visible = state.visible.includes(i);
      if (visible && slot.status !== 'ready') loader.showPoster(slot, routeData.camera.horizontal_fov_deg, routeData.camera.design_aspect);
      if (slot.holder.visible !== visible) { slot.holder.visible = visible; slot.module?.setVisible(visible); dirty = true; }
      if (slot.poster) slot.poster.visible = visible;
      if (!slot.module) continue;
      // Live only at rest under the camera; frozen everywhere else (and while paused).
      const live = i === state.rest && !paused;
      if (slot.frozen === live) { slot.frozen = !live; slot.module.setFrozen(!live); dirty = true; }
      const target = live ? 0 : 1;
      if (slot.grey !== target) {
        slot.grey = target > slot.grey ? Math.min(target, slot.grey + dt / GREY_SECONDS) : Math.max(target, slot.grey - dt / GREY_SECONDS);
        slot.module.setGrey(slot.grey);
        dirty = true;
      }
      if (visible && slot.module.update(dt)) animating = true;
    }
    for (const journey of journeys) {
      if (!journey.current) continue;
      const visible = state.visible.includes(journey.k) && state.visible.includes(journey.k + 1);
      if (journey.current.points.visible !== visible) { journey.current.points.visible = visible; dirty = true; }
      if (visible && !paused && (state.rest === journey.k || state.rest === journey.k + 1)) { journey.time.value += dt; animating = true; }
    }
    if (!dirty && !animating) { streak = 0; return; }
    dirty = false;
    renderer.render(scene, camera);

    // Quality guard over continuous rendering: lower the pixel ratio, then give up.
    streak++; streakTime += wall;
    if (streak >= 90) {
      diagnostics.fps = streak / streakTime;
      slowFor = diagnostics.fps < 24 ? slowFor + streakTime : 0;
      if (slowFor > 5 && quality > 1) { quality = 1; resize(); slowFor = 0; }
      else if (slowFor > 8) { fail(Error('Sustained low frame rate')); return; }
      streak = 0; streakTime = 0;
    }
    Object.assign(diagnostics, {
      phase: state.phase, stop: state.stop, live: state.rest, progress: +state.progress.toFixed(3),
      drawCalls: renderer.info.render.calls, triangles: renderer.info.render.triangles, points: renderer.info.render.points,
      pixelRatio: renderer.getPixelRatio(), loaded: loader.slots.filter(s => s.status === 'ready').map(s => s.stop.id),
    });
  }
  // canvas.routeDiagnostics in the console; heroDiagnostics kept as the old name.
  for (const name of ['routeDiagnostics', 'heroDiagnostics']) Object.defineProperty(canvas, name, { get: () => ({ ...diagnostics }) });
  raf = requestAnimationFrame(frame);

  function dispose() {
    if (disposed) return;
    disposed = true;
    cancelAnimationFrame(raf);
    cleanup.forEach(fn => fn());
    dots.dispose();
    for (const journey of journeys) if (journey.current) { scene.remove(journey.current.points); journey.current.dispose(); }
    loader.dispose();
    renderer.dispose();
    renderer.forceContextLoss();
    canvas.remove();
  }
  function fail(error) { dispose(); onFailure(error); }

  return { dispose, invalidate: () => { dirty = true; } };
}
