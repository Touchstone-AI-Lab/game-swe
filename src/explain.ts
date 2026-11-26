// Animated explainers: before/after sliders for the task examples, and the four-stage harness run.
const reduced = matchMedia('(prefers-reduced-motion: reduce)');

// Run `tick` on every frame while `el` is on screen and the tab is visible.
function whileVisible(el: Element, tick: (now: number) => void) {
  let on = false, raf = 0;
  const loop = (now: number) => { tick(now); raf = requestAnimationFrame(loop); };
  const sync = () => {
    const run = on && !document.hidden && !reduced.matches;
    if (run && !raf) raf = requestAnimationFrame(loop);
    if (!run && raf) { cancelAnimationFrame(raf); raf = 0; }
  };
  new IntersectionObserver(([e]) => { on = e.isIntersecting; sync(); }, { threshold: 0.25 }).observe(el);
  document.addEventListener('visibilitychange', sync);
  return sync;
}

/* Before/after: the handle sweeps by itself until someone touches it */
function initCompare(box: HTMLElement) {
  const ex = box.closest('.ex')!;
  const range = box.querySelector<HTMLInputElement>('.c-range')!;
  const bad = box.querySelector<HTMLElement>('.c-tag.bad')!;
  const good = box.querySelector<HTMLElement>('.c-tag.good')!;
  const set = (p: number) => {
    box.style.setProperty('--pos', `${p}%`);
    range.value = String(Math.round(p));
    bad.style.opacity = String(Math.min(1, Math.max(0, (p - 12) / 22)));
    good.style.opacity = String(Math.min(1, Math.max(0, (88 - p) / 22)));
    ex.classList.toggle('show-before', p > 62);
    ex.classList.toggle('show-after', p < 38);
  };
  let auto = true;
  const t0 = performance.now() + Math.random() * 1500;
  // Ease between the two ends with a pause at each: before (90%) and after (10%).
  whileVisible(box, (now) => {
    if (!auto) return;
    const ph = (((now - t0) / 7000) % 1 + 1) % 1;
    const k = ph < 0.18 ? 0 : ph < 0.5 ? (ph - 0.18) / 0.32 : ph < 0.68 ? 1 : 1 - (ph - 0.68) / 0.32;
    const e = k * k * (3 - 2 * k);
    set(90 - 80 * e);
  });
  const stop = () => { auto = false; };
  range.addEventListener('pointerdown', stop);
  range.addEventListener('keydown', stop);
  range.addEventListener('input', () => { auto = false; set(+range.value); });
  set(reduced.matches ? 50 : 90);
}

/* Harness run: four tabs, each with a progress bar, auto-advancing while in view */
function initRun(run: HTMLElement) {
  const tabs = [...run.querySelectorAll<HTMLButtonElement>('.run-steps [role=tab]')];
  const panes = tabs.map((t) => document.getElementById(t.getAttribute('aria-controls')!)!);
  const bars = tabs.map((t) => t.querySelector<HTMLElement>('.rs-bar i')!);
  let step = 0, elapsed = 0, last = 0, auto = true, hold = false;

  const show = (i: number) => {
    step = i; elapsed = 0;
    tabs.forEach((t, j) => {
      t.setAttribute('aria-selected', String(j === i));
      t.tabIndex = j === i ? 0 : -1;
      t.classList.toggle('done', auto && j < i);
      bars[j].style.setProperty('--p', j < i && auto ? '1' : '0');
    });
    panes.forEach((p, j) => {
      p.hidden = j !== i;
      p.classList.remove('on');
    });
    void panes[i].offsetWidth; // restart the pane's CSS animations
    panes[i].classList.add('on');
  };
  const pick = (i: number) => { auto = false; run.classList.add('manual'); show(i); bars[i].style.setProperty('--p', '1'); };

  tabs.forEach((t, i) => {
    t.addEventListener('click', () => pick(i));
    t.addEventListener('keydown', (e) => {
      const d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
      if (!d) return;
      const n = (i + d + tabs.length) % tabs.length;
      tabs[n].focus(); pick(n);
    });
  });
  run.addEventListener('pointerenter', (e) => { if (e.pointerType === 'mouse') hold = true; });
  run.addEventListener('pointerleave', () => { hold = false; });

  const sync = whileVisible(run, (now) => {
    const dt = last ? Math.min(64, now - last) : 0;
    last = now;
    if (!auto || hold) return;
    const ms = +(tabs[step].dataset.ms ?? 4000);
    elapsed += dt;
    bars[step].style.setProperty('--p', String(Math.min(1, elapsed / ms)));
    if (elapsed >= ms + 500) show((step + 1) % tabs.length);
  });
  // Restart the pane animation when the run scrolls back into view.
  new IntersectionObserver(([e]) => { if (e.isIntersecting && auto) { last = 0; show(step); } sync(); }, { threshold: 0.25 }).observe(run);
  if (reduced.matches) auto = false;
  show(0);
}

export function initExplainers() {
  document.querySelectorAll<HTMLElement>('[data-compare]').forEach(initCompare);
  const run = document.getElementById('run');
  if (run) initRun(run);
}
