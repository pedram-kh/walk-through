// Decides between the live 3D hero and the still image, and pauses when unseen.
const stage = document.querySelector('#stage');
const pauseButton = document.querySelector('#pause');
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
const finePointer = matchMedia('(pointer: fine)');

let live = null, loading = false, failed = false, onScreen = true, paused = false;

const eligible = () => finePointer.matches && !reduced.matches && !navigator.connection?.saveData;

function showStill(error) {
  live?.dispose();
  live = null;
  stage.classList.remove('ready');
  pauseButton.hidden = true;
  if (error) { failed = true; console.warn('Hero still fallback:', error.message); }
}

function sync() {
  if (!eligible()) { showStill(); return; }
  if (live) { live.setActive(onScreen && !document.hidden && !paused); return; }
  if (loading || failed) return;
  loading = true;
  import('./hero.js')
    .then(m => m.createHero(stage, showStill))
    .then(hero => {
      if (!eligible()) { hero.dispose(); return; }
      live = hero;
      stage.classList.add('ready');
      pauseButton.hidden = false;
      sync();
    })
    .catch(showStill)
    .finally(() => { loading = false; });
}

pauseButton.addEventListener('click', () => {
  paused = !paused;
  pauseButton.textContent = paused ? 'Resume motion' : 'Pause motion';
  pauseButton.setAttribute('aria-pressed', String(paused));
  sync();
});
reduced.addEventListener('change', sync);
finePointer.addEventListener('change', sync);
document.addEventListener('visibilitychange', sync);
new IntersectionObserver(entries => { onScreen = entries[0].isIntersecting; sync(); }, { threshold: 0.05 }).observe(stage);
sync();
