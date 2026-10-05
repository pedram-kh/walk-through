// Chooses between the 3D walk-through and the flat page.
// Touch devices, reduced motion, data saver and any graphics failure get the flat page.
const html = document.documentElement;
const stage = document.querySelector('#stage');
const overlay = document.querySelector('#tags');
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
const finePointer = matchMedia('(pointer: fine)');

let route = null, loading = false, failed = false;

const eligible = () => finePointer.matches && !reduced.matches && !navigator.connection?.saveData;

function showFlat(error) {
  route?.dispose();
  route = null;
  html.classList.remove('route', 'route-ready');
  if (error) { failed = true; console.warn('Flat page fallback:', error.message); }
}

function sync() {
  if (!eligible()) { showFlat(); return; }
  if (route || loading || failed) return;
  loading = true;
  html.classList.add('route');            // spacers open up before the route measures the page
  import('./runtime/runtime.js')
    .then(m => m.startRoute({ stage, overlay, isPaused: () => false, onFailure: showFlat }))
    .then(started => {
      if (!eligible()) { started.dispose(); showFlat(); return; }
      route = started;
      html.classList.add('route-ready');
      if (new URLSearchParams(location.search).has('bench')) import('./runtime/bench.js').then(b => b.runBench());
    })
    .catch(showFlat)
    .finally(() => { loading = false; });
}

reduced.addEventListener('change', sync);
finePointer.addEventListener('change', sync);
sync();
