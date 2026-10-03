// Stop loading: each stop is its own download (stops/<id>/stop.js and its files).
// Around the camera's stop N we keep N-2 .. N+2 loaded, nearest first; anything
// further behind is disposed and reloaded if the visitor scrolls back. A stop that
// is needed on screen before it has loaded shows its poster on a plane instead.
import * as THREE from 'three';

const KEEP_BEHIND = 2, LOAD_AHEAD = 2;
const POSTER_DISTANCE = 11;   // how far in front of the rest view the poster plane sits

export class StopLoader {
  constructor({ route, scene, camera, makeContext, onLoaded, onError }) {
    Object.assign(this, { route, scene, camera, makeContext, onLoaded, onError });
    this.slots = route.stops.map(stop => {
      const holder = new THREE.Group();          // places the stop in the world
      holder.position.copy(stop.origin);
      holder.quaternion.copy(stop.quaternion);
      holder.visible = false;
      scene.add(holder);
      return { stop, holder, status: 'idle', module: null, poster: null };
    });
    this.loading = null;
  }

  // Keep the window around stop `index` loaded; load one stop at a time, nearest first.
  focus(index) {
    for (const [i, slot] of this.slots.entries()) {
      if (slot.status === 'ready' && i < index - KEEP_BEHIND) this.unload(slot);
    }
    if (this.loading) return;
    const wanted = [index, index + 1, index - 1, index + 2, index - 2]
      .filter(i => i >= 0 && i < this.slots.length && i <= index + LOAD_AHEAD);
    const next = wanted.map(i => this.slots[i]).find(slot => slot.status === 'idle');
    if (next) this.loading = this.load(next).finally(() => { this.loading = null; this.focus(index); });
  }

  async load(slot) {
    slot.status = 'loading';
    try {
      const module = await import(`../${slot.stop.dir}stop.js`);
      const stop = await module.load(this.makeContext(slot));
      if (slot.status !== 'loading') { stop.dispose(); return; }   // unloaded while loading
      slot.module = stop;
      slot.status = 'ready';
      slot.holder.add(stop.group);
      this.removePoster(slot);
      this.onLoaded(slot);
    } catch (error) {
      slot.status = 'failed';
      this.onError(slot, error);
    }
  }

  unload(slot) {
    slot.module?.dispose();
    if (slot.module) slot.holder.remove(slot.module.group);
    slot.module = null;
    slot.status = 'idle';
  }

  // Poster stand-in for a stop that must be seen before it is ready.
  showPoster(slot, fov, aspect) {
    if (slot.poster || slot.status === 'ready') return;
    const width = 2 * POSTER_DISTANCE * Math.tan(THREE.MathUtils.degToRad(fov) / 2), height = width / aspect;
    const material = new THREE.MeshBasicMaterial({ color: 0x555555 });
    new THREE.TextureLoader().load(slot.stop.poster, texture => {
      texture.colorSpace = THREE.SRGBColorSpace;
      material.map = texture; material.color.set(0xffffff); material.needsUpdate = true;
    });
    const plane = new THREE.Mesh(new THREE.PlaneGeometry(width, height), material);
    plane.quaternion.copy(slot.stop.restQuaternion);
    plane.position.copy(slot.stop.restPosition).add(new THREE.Vector3(0, 0, -POSTER_DISTANCE).applyQuaternion(slot.stop.restQuaternion));
    this.scene.add(plane);
    slot.poster = plane;
  }

  removePoster(slot) {
    if (!slot.poster) return;
    this.scene.remove(slot.poster);
    slot.poster.geometry.dispose(); slot.poster.material.map?.dispose(); slot.poster.material.dispose();
    slot.poster = null;
  }

  dispose() {
    for (const slot of this.slots) { this.removePoster(slot); this.unload(slot); this.scene.remove(slot.holder); }
  }
}
