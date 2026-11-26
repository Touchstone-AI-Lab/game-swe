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

/* rhenium sessions on SG-105: validate the task, then two real agent attempts.
   Commands and output formats are the real CLI's; output is trimmed with jq and the task key is masked. */
type Line = {
  cmd?: string; // typed at the prompt
  out?: string; // printed output (trusted markup)
  ms?: number; // wait before an output line appears
  k?: string; // checklist item this line starts
  fin?: 'done' | 'fail'; // settles the active checklist item
};
type Script = { base: number; lines: Line[] };

const MASK = '█████████';
const KEY = `minecraft/construct/${MASK}`;
const esc = (s: string) => s.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' })[c]!);
const dim = (s: string) => `<span class="t-m">${esc(s)}</span>`;
// jq -c output, coloured the way jq colours a terminal: keys muted, statuses by meaning.
const json = (o: Record<string, unknown>) => `<span class="t-m">{</span>${Object.entries(o).map(([k, v]) => {
  // Numbers arrive as strings so they keep jq's "10.0" form; they print without quotes.
  const val = typeof v === 'string' && !/^-?\d+(\.\d+)?$/.test(v)
    ? `<span class="${v === 'passed' || v === 'Submitted' ? 't-g' : v === 'failed' ? 't-r' : 't-s'}">"${esc(v)}"</span>`
    : `<span class="${v === true ? 't-g' : 't-n'}">${String(v)}</span>`;
  return `<span class="t-k">"${k}"</span><span class="t-m">:</span>${val}`;
}).join('<span class="t-m">,</span>')}<span class="t-m">}</span>`;
const pct = (n: number, phase: string, ms = 140) => ({ out: `${dim(`[${String(n).padStart(3)}%]`)} ${esc(phase)}`, ms });
const step = (n: number) => pct(Math.min(85, 10 + Math.floor((n / 100) * 70)), `mini-swe-agent step ${n}`, 650);
const checks = (shape: string, build: [string, string], live: [string, string]) => [
  { out: json({ id: 'submission-shape', status: shape, score: '0.0' }), ms: 120 },
  { out: json({ id: 'offline-build', status: build[0], score: build[1] }), ms: 60 },
  { out: json({ id: 'upstream-tests', status: 'skipped', score: '0.0' }), ms: 60 },
  { out: json({ id: 'live-server', status: live[0], score: live[1] }), ms: 60 },
];
const agent = (model: string, steps: number, pass: boolean): Script => ({
  base: 4,
  lines: [
    { cmd: `export TASK=${KEY}   # SG-105` },
    { cmd: `# model under test: ${model}, through mini-swe-agent` },
    { k: 'agent', cmd: "rhenium benchmark $TASK --provider api | jq -c '.tasks[]|{status,score,agentExit}'" },
    { out: `${dim('==')} [1/1] ${esc(KEY)} (api)`, ms: 500 },
    pct(5, 'preparing task workspace', 400),
    step(1), step(2),
    { out: dim('⋮'), ms: 500 },
    step(steps),
    { k: 'score', ...pct(88, 'running private evaluation', 700) },
    pct(100, 'complete', 2400),
    { out: pass ? `   <span class="t-g">passed</span>  score=100.0` : `   <span class="t-r">failed</span>  score=10.0`, ms: 200, fin: pass ? 'done' : 'fail' },
    { out: json({ status: pass ? 'passed' : 'failed', score: pass ? '100.0' : '10.0', agentExit: 'Submitted' }), ms: 120 },
    { cmd: pass ? '# resolved: every in-game case passes' : '# submitted as done; it builds, but an in-game case fails' },
  ],
});
const SCRIPTS: Record<string, Script> = {
  validate: {
    base: 0,
    lines: [
      { k: 'rt', cmd: "rhenium runtime prepare minecraft/paper-1.21.11-132-construct | jq -c '{key,ready}'" },
      pct(5, 'acquiring licensed runtime source', 500),
      pct(65, 'building evaluator artifact', 1400),
      pct(100, 'runtime ready', 1400),
      { out: `<span class="t-m">{</span><span class="t-k">"key"</span><span class="t-m">:</span><span class="t-s">"minecraft/paper-1.21.11-132-construct"</span><span class="t-m">,</span><span class="t-k">"ready"</span><span class="t-m">:</span><span class="t-g">true</span><span class="t-m">}</span>`, ms: 150 },
      { cmd: `export TASK=${KEY}   # SG-105, key withheld` },
      { k: 'ref', cmd: "rhenium run $TASK ./reference | jq -c '.result.checks[]|{id,status,score}'" },
      ...checks('passed', ['passed', '10.0'], ['passed', '90.0']).map((l, i) => (i ? l : { ...l, ms: 2200 })),
      { k: 'start', cmd: "rhenium run $TASK ./starter | jq -c '.result.checks[]|{id,status,score}'" },
      ...checks('passed', ['passed', '10.0'], ['failed', '0.0']).map((l, i) => (i ? l : { ...l, ms: 2200 })),
      { k: 'play', cmd: '# next: a human plays SG-105 through in the game' },
    ],
  },
  opus: agent('Claude Opus 5.5', 6, false),
  astra: agent('GPT-6 Astra', 11, true),
};
const NEXT: Record<string, string> = { validate: 'opus', opus: 'astra', astra: 'validate' };
const CHAR_MS = 26;
const lineMs = (l: Line) => (l.cmd ? 380 + l.cmd.length * CHAR_MS + 220 : l.ms ?? 120);

function renderLines(body: HTMLElement, lines: Line[]) {
  body.innerHTML = lines.map((l) => (l.cmd
    ? `<p class="tl cmd${l.cmd.startsWith('#') ? ' note' : ''}"><span class="ty"></span><span class="rest"></span></p>`
    : `<p class="tl out"><span class="c">${l.out}</span></p>`)).join('');
  const ps = [...body.children] as HTMLElement[];
  lines.forEach((l, i) => { if (l.cmd) ps[i].querySelector('.rest')!.textContent = l.cmd; });
  return ps;
}

function initAuthor(root: HTMLElement) {
  const body = root.querySelector<HTMLElement>('#author-out')!;
  const tabs = [...root.querySelectorAll<HTMLButtonElement>('.tw-tabs [role=tab]')];
  const replay = root.querySelector<HTMLButtonElement>('#author-replay')!;
  const items = [...document.querySelectorAll<HTMLElement>('#author-checks li')];
  const order = items.map((c) => c.dataset.k!);
  const caret = document.createElement('i');
  caret.className = 'caret';

  let name = 'validate', script = SCRIPTS.validate, ps: HTMLElement[] = [];
  let idx = 0, t = 0, hold = 0, auto = true, last = 0, active = -1;

  const activate = (k: string) => {
    const at = order.indexOf(k);
    items.forEach((c, j) => {
      if (j < at && !c.classList.contains('fail')) { c.classList.remove('on'); c.classList.add('done'); }
      c.classList.toggle('on', j === at);
    });
    active = at;
  };
  const settle = (how: 'done' | 'fail') => {
    if (active < 0) return;
    items[active].classList.remove('on');
    items[active].classList.add(how);
    active = -1;
  };
  const finishLine = (i: number) => {
    const l = script.lines[i], p = ps[i];
    p.classList.add('show', 'full');
    if (l.cmd) { p.querySelector('.ty')!.textContent = l.cmd; p.querySelector('.rest')!.textContent = ''; }
  };
  const load = (n: string) => {
    name = n; script = SCRIPTS[n]; ps = renderLines(body, script.lines);
    idx = 0; t = 0; hold = 0; active = -1;
    tabs.forEach((b) => { const on = b.dataset.script === n; b.setAttribute('aria-selected', String(on)); b.tabIndex = on ? 0 : -1; });
    root.classList.remove('finished');
    items.forEach((c, j) => { c.classList.remove('on', 'fail'); c.classList.toggle('done', j < script.base); });
    if (reduced.matches) {
      script.lines.forEach((l, i) => { if (l.k) activate(l.k); if (l.fin) settle(l.fin); finishLine(i); });
      settle('done');
      idx = script.lines.length;
      root.classList.add('finished');
    }
  };

  // Reserve the height of the longest session so the page does not jump.
  const fit = () => {
    const probe = body.cloneNode() as HTMLElement;
    probe.removeAttribute('id');
    probe.style.cssText = 'position:absolute;visibility:hidden;left:0;right:0;top:0;min-height:0';
    root.append(probe);
    let h = 0;
    for (const k of Object.keys(SCRIPTS)) {
      renderLines(probe, SCRIPTS[k].lines).forEach((p, i) => {
        p.classList.add('show', 'full');
        const l = SCRIPTS[k].lines[i];
        if (l.cmd) { p.querySelector('.ty')!.textContent = l.cmd; p.querySelector('.rest')!.textContent = ''; }
      });
      h = Math.max(h, probe.offsetHeight);
    }
    probe.remove();
    body.style.minHeight = `${h}px`;
  };

  const tick = (dt: number) => {
    const lines = script.lines;
    if (idx >= lines.length) {
      if (!auto) return;
      hold += dt;
      if (hold > 4500) load(NEXT[name]);
      return;
    }
    t += dt;
    while (idx < lines.length) {
      const l = lines[idx], p = ps[idx], need = lineMs(l);
      if (!p.classList.contains('show')) {
        p.classList.add('show');
        if (l.k) activate(l.k);
      }
      if (t < need) {
        if (l.cmd) {
          const n = Math.max(0, Math.min(l.cmd.length, Math.floor((t - 380) / CHAR_MS)));
          const ty = p.querySelector('.ty')!;
          ty.textContent = l.cmd.slice(0, n);
          ty.append(caret);
          p.querySelector('.rest')!.textContent = l.cmd.slice(n);
        } else {
          p.prepend(caret); // the cursor waits on the empty line while the command runs
        }
        return;
      }
      t -= need;
      finishLine(idx);
      if (l.fin) settle(l.fin);
      idx++;
    }
    caret.remove();
    settle('done');
    root.classList.add('finished');
  };

  whileVisible(root, (now) => {
    const dt = last ? Math.min(64, now - last) : 0;
    last = now;
    tick(dt);
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
  load('validate');
}

export function initExplainers() {
  document.querySelectorAll<HTMLElement>('[data-compare]').forEach(initCompare);
  const run = document.getElementById('run');
  if (run) initRun(run);
  const author = document.getElementById('author');
  if (author) initAuthor(author);
}
