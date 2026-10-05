// Route: maps the page's scroll position to the camera pose and the transition phase.
// Scroll ranges come from measuring the section and spacer elements, so they adapt to
// any screen. For a move from stop N to N+1 (see PLAN.md, phases A-H):
//   section N held on screen        -> rest at stop N, live; scrolling through its hold zone
//                                      (an extra half screen, the section sticky) fills the pill
//   section N scrolling up          -> curtain; camera still at stop N's rest view
//   spacer N fills the screen       -> curl and travel along the segment samples
//   section N+1 scrolling up        -> camera at stop N+1's rest view
import * as THREE from 'three';

const REST_TOLERANCE = 4;     // px: how close to a rest position still counts as "at rest"

export class Route {
  constructor(data) {
    this.data = data;
    this.stops = data.stops.map(stop => ({
      ...stop,
      origin: new THREE.Vector3().fromArray(stop.origin),
      quaternion: new THREE.Quaternion().fromArray(stop.quaternion),
      restPosition: new THREE.Vector3().fromArray(stop.rest.position),
      restQuaternion: new THREE.Quaternion().fromArray(stop.rest.quaternion),
      section: document.getElementById(stop.section),
    }));
    for (const stop of this.stops) stop.hold = stop.section?.closest('.hold') ?? stop.section;   // the hold wrapper
    this.segments = data.segments.map(segment => ({
      ...segment,
      positions: segment.position.map(p => new THREE.Vector3().fromArray(p)),
      quaternions: segment.quaternion.map(q => new THREE.Quaternion().fromArray(q)),
      spacer_id: segment.spacer,
      spacer: document.getElementById(segment.spacer),
    }));
    for (const stop of this.stops) if (!stop.section) throw Error('Section missing from the page: #' + data.stops[this.stops.indexOf(stop)].section);
    for (const segment of this.segments) {
      if (!segment.spacer) throw Error('Spacer missing from the page: #' + segment.spacer_id);
      segment.spacer.style.setProperty('--screens', segment.spacer_screens);   // journey length, from route.json
    }
    this.measure();
  }

  // Page positions of every section and spacer; call on resize and layout changes.
  measure() {
    const top = el => el.getBoundingClientRect().top + window.scrollY;
    this.viewport = window.innerHeight;
    for (const stop of this.stops) {
      // At rest from the moment the section fills the screen until its hold wrapper ends
      // (the section is sticky inside it). Measured on the wrapper: a sticky section moves.
      const t = top(stop.hold), h = stop.hold.offsetHeight;
      stop.restFrom = Math.min(t, t + h - this.viewport);
      stop.restTo = Math.max(t, t + h - this.viewport);
    }
    for (const segment of this.segments) {
      segment.travelFrom = top(segment.spacer);
      segment.travelTo = segment.travelFrom + Math.max(1, segment.spacer.offsetHeight - this.viewport);
    }
  }

  // The hold zone the scroll position is in (or -1): for the scroll brake.
  holdAt(scrollY) {
    return this.stops.findIndex(stop => scrollY >= stop.restFrom - REST_TOLERANCE && scrollY < stop.restTo);
  }

  // If scrolling from `from` to `to` would enter a hold zone past its edge, that edge (the zone's
  // start going down, its end going up); otherwise null.
  entryBetween(from, to) {
    if (to > from) {                            // going down: the first zone below
      for (const stop of this.stops) if (from < stop.restFrom - 1 && to > stop.restFrom) return stop.restFrom;
    } else if (to < from) {                     // going up: the first zone above
      for (const stop of [...this.stops].reverse()) if (from > stop.restTo + 1 && to < stop.restTo) return stop.restTo;
    }
    return null;
  }

  // Scroll position at which a stop is at rest (where the dots fly to): the start of its hold zone.
  restScroll(index) { return Math.max(0, this.stops[index].restFrom); }

  // Camera pose and phase for a scroll position.
  at(scrollY, pose) {
    for (let k = 0; k < this.segments.length; k++) {
      const segment = this.segments[k];
      if (scrollY > segment.travelFrom && scrollY < segment.travelTo) {
        const progress = (scrollY - segment.travelFrom) / (segment.travelTo - segment.travelFrom);
        const f = progress * (segment.positions.length - 1), i = Math.min(Math.floor(f), segment.positions.length - 2);
        pose.position.lerpVectors(segment.positions[i], segment.positions[i + 1], f - i);
        pose.quaternion.slerpQuaternions(segment.quaternions[i], segment.quaternions[i + 1], f - i);
        return { phase: 'travel', segment: k, progress, stop: progress < 0.5 ? k : k + 1, rest: -1, hold: 0, visible: [k, k + 1] };
      }
    }
    // Not travelling: the camera rests at the stop whose stretch of page this is.
    let index = 0;
    while (index < this.segments.length && scrollY >= this.segments[index].travelTo) index++;
    const stop = this.stops[index];
    pose.position.copy(stop.restPosition);
    pose.quaternion.copy(stop.restQuaternion);
    const atRest = scrollY >= stop.restFrom - REST_TOLERANCE && scrollY <= stop.restTo + REST_TOLERANCE;
    const hold = Math.min(1, Math.max(0, (scrollY - stop.restFrom) / Math.max(1, stop.restTo - stop.restFrom)));
    return { phase: atRest ? 'rest' : 'curtain', segment: -1, progress: 0, stop: index, rest: atRest ? index : -1,
             hold: atRest ? hold : 0,
             visible: [index - 1, index, index + 1].filter(i => i >= 0 && i < this.stops.length) };
  }
}
