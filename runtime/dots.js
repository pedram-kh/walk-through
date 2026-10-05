// Progress dots: one per stop, vertical, on the left. Clicking one flies there (to the start
// of its hold zone) by scrolling the page, so the camera passes through every stop on the way.
// In a stop's hold zone its dot becomes a pill that fills as the visitor scrolls through.
const SECONDS_PER_STOP = 0.9, MAX_SECONDS = 4;

export function mountDots(route) {
  const nav = document.createElement('nav');
  nav.className = 'route-dots';
  nav.setAttribute('aria-label', 'Sections');
  const buttons = route.stops.map((stop, index) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.setAttribute('aria-label', `${index + 1}: ${stop.section.dataset.title ?? stop.id}`);
    button.addEventListener('click', () => flyTo(index));
    nav.append(button);
    return button;
  });
  document.body.append(nav);

  let flight = 0, current = -1, holding = -1, fill = -1;
  const cancel = () => { cancelAnimationFrame(flight); flight = 0; document.documentElement.classList.remove('flying'); };
  const interrupt = e => { if (flight && !(e.type === 'pointerdown' && nav.contains(e.target))) cancel(); };
  const interruptions = ['wheel', 'touchstart', 'keydown', 'pointerdown'];
  for (const type of interruptions) addEventListener(type, interrupt, { passive: true });

  function flyTo(index) {
    cancel();
    const from = scrollY, to = route.restScroll(index);
    if (Math.abs(to - from) < 2) return;
    const stops = Math.max(1, Math.abs(index - Math.max(current, 0)));
    const duration = Math.min(MAX_SECONDS, SECONDS_PER_STOP * stops + 0.4) * 1000;
    document.documentElement.classList.add('flying');      // no scroll brake during the flight
    const start = performance.now();
    const step = now => {
      const t = Math.min(1, (now - start) / duration), eased = t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2;
      scrollTo(0, from + (to - from) * eased);
      if (t < 1) flight = requestAnimationFrame(step);
      else { cancel(); buttons[index].focus({ preventScroll: true }); }
    };
    flight = requestAnimationFrame(step);
  }

  return {
    // The stop the camera belongs to right now.
    setCurrent(index) {
      if (index === current) return;
      current = index;
      buttons.forEach((b, i) => i === index ? b.setAttribute('aria-current', 'step') : b.removeAttribute('aria-current'));
    },
    // The stop whose hold zone the scroll is in (-1: none) and how far through it (0..1).
    setHold(index, progress) {
      if (index !== holding) {
        buttons[holding]?.classList.remove('hold');
        buttons[index]?.classList.add('hold');
        holding = index;
      }
      const value = index < 0 ? 0 : Math.round(progress * 200) / 200;
      if (value !== fill && index >= 0) { fill = value; buttons[index].style.setProperty('--fill', String(value)); }
    },
    dispose() {
      cancel();
      for (const type of interruptions) removeEventListener(type, interrupt);
      nav.remove();
    },
  };
}
