// ?bench: drives the route on its own and measures frame rate per stop and phase.
// Rest at each stop, travel between them, then come back. Results go to the console
// (console.table) and to window.benchResult, ready to copy into PLAN.md.
const REST_SECONDS = 4, TRAVEL_SECONDS = 8;

export async function runBench() {
  const canvas = document.querySelector('#stage canvas');
  const diag = () => canvas.routeDiagnostics;
  const sections = [...document.querySelectorAll('main > .section')];
  const restAt = el => el.getBoundingClientRect().top + scrollY;
  const groups = new Map();
  let last = 0, running = true;
  const sample = now => {
    if (!running) return;
    if (last) {
      const d = diag(), key = `${d.phase === 'travel' ? 'travel' : 'stop'} ${d.phase === 'travel' ? `${d.stop}` : `${d.stop + 1} ${d.phase}`}`;
      const g = groups.get(key) ?? { frames: 0, seconds: 0, worst: 0 };
      const dt = (now - last) / 1000;
      g.frames++; g.seconds += dt; g.worst = Math.max(g.worst, dt);
      groups.set(key, g);
    }
    last = now;
    requestAnimationFrame(sample);
  };
  const wait = s => new Promise(r => setTimeout(r, s * 1000));
  const glide = (to, seconds) => new Promise(resolve => {
    const from = scrollY, start = performance.now();
    const step = now => {
      const t = Math.min(1, (now - start) / (seconds * 1000));
      scrollTo(0, from + (to - from) * t);
      if (t < 1) requestAnimationFrame(step); else resolve();
    };
    requestAnimationFrame(step);
  });

  console.info('Bench: running (keep this tab in front and the mouse still)...');
  document.documentElement.classList.add('flying');           // no snapping while gliding
  scrollTo(0, 0);
  await wait(1);
  requestAnimationFrame(sample);
  for (let i = 0; i < sections.length; i++) {
    if (i > 0) await glide(restAt(sections[i]), TRAVEL_SECONDS);
    await wait(REST_SECONDS);
  }
  for (let i = sections.length - 2; i >= 0; i--) {
    await glide(restAt(sections[i]), TRAVEL_SECONDS);
    await wait(1);
  }
  running = false;
  document.documentElement.classList.remove('flying');
  const rows = [...groups].map(([phase, g]) => ({ phase, fps: +(g.frames / g.seconds).toFixed(1), worstFrameMs: Math.round(g.worst * 1000), seconds: +g.seconds.toFixed(1) }));
  window.benchResult = { date: new Date().toISOString().slice(0, 10), pixelRatio: diag().pixelRatio, rows };
  console.table(rows);
  return window.benchResult;
}
