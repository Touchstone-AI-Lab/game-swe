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

/* Task authoring: a typed terminal session, with the checklist beside it following along */
type Line = { k?: string; cmd?: string; out?: string; spin?: [string, string]; done?: string };
const m = (s: string) => `<span class="t-m">${s}</span>`;
const ok = '<span class="t-g">✓</span>', no = '<span class="t-r">✗</span>';
const f2p = (s: string) => `<span class="tk f2p">F2P</span> ${s}`, p2p = (s: string) => `<span class="tk p2p">P2P</span> ${s}`;
const SCRIPTS: Record<string, Line[]> = {
  repair: [
    { k: 'source', cmd: 'new-task stardew-valley --repair --mod Automate' },
    { out: `${m('source   ')} Automate · open source · license recorded` },
    { k: 'task', out: `${m('initial  ')} item bugs: duplicate, repeated, lost output` },
    { out: `${m('reference')} the working version of the mod` },
    { k: 'tests', cmd: 'add-tests' },
    { out: f2p('no duplicate output') },
    { out: f2p('no repeated collection') },
    { out: f2p('10 stored + 1 produced = 11 total') },
    { out: p2p('normal machine output still delivered') },
    { k: 'ref', cmd: 'validate --solution reference' },
    { spin: ['booting Stardew Valley + SMAPI', 'ready'] },
    { out: `${ok} F2P 3/3   ${ok} P2P 1/1   <span class="t-g">all pass</span>` },
    { k: 'init', cmd: 'validate --solution initial' },
    { spin: ['booting Stardew Valley + SMAPI', 'ready'] },
    { out: `${no} F2P 0/3 ${m('(must fail)')}   ${ok} P2P 1/1   <span class="t-g">valid</span>` },
    { k: 'play', cmd: 'playtest' },
    { spin: ['a reviewer plays it through in game', 'confirmed'] },
    { done: 'SG-062 accepted' },
  ],
  construct: [
    { k: 'source', cmd: 'new-task minecraft --construct --feature BlockTrail' },
    { out: `${m('source   ')} open-source plugin · license recorded` },
    { k: 'task', out: `${m('initial  ')} an empty Paper plugin project` },
    { out: `${m('reference')} block logging and rollback, written for the task` },
    { k: 'tests', cmd: 'add-tests' },
    { out: f2p('rollback restores the wall after TNT') },
    { out: f2p('filter by actor, area and time') },
    { out: f2p('undo marks persist across reloads') },
    { out: f2p('never roll back twice') },
    { out: m('no P2P tests: the project starts empty') },
    { k: 'ref', cmd: 'validate --solution reference' },
    { spin: ['starting the Paper server', 'ready'] },
    { out: `${ok} F2P 4/4   <span class="t-g">all pass</span>` },
    { k: 'init', cmd: 'validate --solution initial' },
    { spin: ['starting the Paper server', 'ready'] },
    { out: `${no} F2P 0/4 ${m('(must fail)')}   <span class="t-g">valid</span>` },
    { k: 'play', cmd: 'playtest' },
    { spin: ['a reviewer plays it through in game', 'confirmed'] },
    { done: 'SG-105 accepted' },
  ],
};
const SPIN = '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏';
const CHAR_MS = 30;
const lineMs = (l: Line) => (l.cmd ? 420 + l.cmd.length * CHAR_MS + 180 : l.spin ? 1250 : l.done ? 450 : 120);

function renderLines(body: HTMLElement, lines: Line[]) {
  body.innerHTML = lines.map((l) => {
    if (l.cmd) return `<p class="tl cmd"><span class="ty"></span><span class="rest"></span></p>`;
    if (l.spin) return `<p class="tl out">${m('▸')} ${l.spin[0]} <span class="sp">${SPIN[0]}</span></p>`;
    if (l.done) return `<p class="tl done"><span>✓</span> ${l.done}</p>`;
    return `<p class="tl out">${l.out}</p>`;
  }).join('');
  const ps = [...body.children] as HTMLElement[];
  lines.forEach((l, i) => { if (l.cmd) ps[i].querySelector('.rest')!.textContent = l.cmd; });
  return ps;
}

function initAuthor(root: HTMLElement) {
  const body = root.querySelector<HTMLElement>('#author-out')!;
  const tabs = [...root.querySelectorAll<HTMLButtonElement>('.tw-tabs [role=tab]')];
  const replay = root.querySelector<HTMLButtonElement>('#author-replay')!;
  const checks = [...document.querySelectorAll<HTMLElement>('#author-checks li')];
  const order = checks.map((c) => c.dataset.k!);
  const caret = document.createElement('i');
  caret.className = 'caret';

  let name = 'repair', lines: Line[] = [], ps: HTMLElement[] = [];
  let idx = 0, t = 0, hold = 0, auto = true, last = 0;

  const mark = (k: string | 'all' | null) => {
    const at = k === 'all' ? order.length : k ? order.indexOf(k) : -1;
    checks.forEach((c, i) => { c.classList.toggle('done', i < at); c.classList.toggle('on', i === at); });
  };
  const finishLine = (i: number) => {
    const l = lines[i], p = ps[i];
    p.classList.add('show');
    if (l.cmd) { p.querySelector('.ty')!.textContent = l.cmd; p.querySelector('.rest')!.textContent = ''; }
    if (l.spin) p.querySelector('.sp')!.outerHTML = `<span class="t-g">${l.spin[1]}</span>`;
  };
  const load = (n: string) => {
    name = n; lines = SCRIPTS[n]; ps = renderLines(body, lines);
    idx = 0; t = 0; hold = 0; last = 0;
    tabs.forEach((b) => { const on = b.dataset.script === n; b.setAttribute('aria-selected', String(on)); b.tabIndex = on ? 0 : -1; });
    root.classList.remove('finished');
    mark(null);
    if (reduced.matches) { lines.forEach((_, i) => finishLine(i)); idx = lines.length; mark('all'); root.classList.add('finished'); }
  };

  // Reserve the height of the longest session so the page does not jump.
  const fit = () => {
    const probe = body.cloneNode() as HTMLElement;
    probe.removeAttribute('id');
    probe.style.cssText = `position:absolute;visibility:hidden;left:0;right:0;top:0;min-height:0`;
    root.append(probe);
    let h = 0;
    for (const k of Object.keys(SCRIPTS)) { renderLines(probe, SCRIPTS[k]).forEach((p) => p.classList.add('show')); h = Math.max(h, probe.offsetHeight); }
    probe.remove();
    body.style.minHeight = `${h}px`;
  };

  const step = (dt: number) => {
    if (idx >= lines.length) {
      if (!auto) return;
      hold += dt;
      if (hold > 4200) load(name === 'repair' ? 'construct' : 'repair');
      return;
    }
    t += dt;
    while (idx < lines.length) {
      const l = lines[idx], p = ps[idx], need = lineMs(l);
      if (!p.classList.contains('show')) {
        p.classList.add('show');
        if (l.k) mark(l.k);
        if (l.done) mark('all');
      }
      if (t < need) {
        if (l.cmd) {
          const n = Math.max(0, Math.min(l.cmd.length, Math.floor((t - 420) / CHAR_MS)));
          const ty = p.querySelector('.ty')!;
          ty.textContent = l.cmd.slice(0, n);
          ty.append(caret);
          p.querySelector('.rest')!.textContent = l.cmd.slice(n);
        } else if (l.spin) {
          p.querySelector('.sp')!.textContent = SPIN[Math.floor(t / 80) % SPIN.length];
        }
        return;
      }
      t -= need;
      finishLine(idx);
      idx++;
    }
    caret.remove();
    root.classList.add('finished');
  };

  whileVisible(root, (now) => {
    const dt = last ? Math.min(64, now - last) : 0;
    last = now;
    step(dt);
  });
  tabs.forEach((b, i) => {
    b.addEventListener('click', () => { auto = false; load(b.dataset.script!); });
    b.addEventListener('keydown', (e) => {
      const d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
      if (!d) return;
      const n = tabs[(i + d + tabs.length) % tabs.length];
      n.focus(); auto = false; load(n.dataset.script!);
    });
  });
  replay.addEventListener('click', () => load(name));
  let rt = 0;
  addEventListener('resize', () => { clearTimeout(rt); rt = window.setTimeout(fit, 200); });
  fit();
  load('repair');
}

export function initExplainers() {
  document.querySelectorAll<HTMLElement>('[data-compare]').forEach(initCompare);
  const run = document.getElementById('run');
  if (run) initRun(run);
  const author = document.getElementById('author');
  if (author) initAuthor(author);
}
