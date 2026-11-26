import './style.css';
import { data, modelBySlug, pct } from './data';
import { initTheme } from './theme';
import { createGlobe } from './globe';
import { initResults } from './results';
import { initExplainers } from './explain';

document.documentElement.classList.add('js');
initTheme();

// Fill every [data-bind] from data.json, so the page has one source for its numbers.
const lookup = (path: string): unknown => path.split('.').reduce<unknown>((o, k) => (o as Record<string, unknown>)?.[k], data);
document.querySelectorAll<HTMLElement>('[data-bind]').forEach((n) => {
  const v = lookup(n.dataset.bind!);
  let s = String(v);
  if (typeof v === 'number') {
    if (n.dataset.fmt === 'pct') s = pct(v);
    else if (n.dataset.fmt === 'round') s = String(Math.round(v));
    else if (n.dataset.fmt === 'int') s = v.toLocaleString('en-US');
    if (n.dataset.pad) s = s.padStart(+n.dataset.pad, '0');
  }
  n.textContent = s;
});

/* Games: globe, detail panel and tiles share one selection */
const games = data.games;
const hero = document.getElementById('hero')!;
const panel = document.getElementById('game-panel')!;
const $ = (id: string) => document.getElementById(id)!;
const names = (slugs: string[]) => slugs.map((s) => modelBySlug.get(s)!.name).join(' & ');
const cover = (slug: string) => `./games/${slug}.webp`;
const thumb = (slug: string) => `./games/${slug}-t.webp`;

function show(slug: string | null) {
  const g = games.find((x) => x.slug === slug);
  hero.classList.toggle('has-game', !!g);
  panel.hidden = !g;
  document.querySelectorAll('.cover').forEach((t) => t.classList.toggle('on', (t as HTMLElement).dataset.game === slug));
  if (!g) {
    $('readout-main').textContent = 'Select a game';
    $('readout-sub').textContent = 'Click a label · drag to explore';
    history.replaceState(null, '', location.pathname + location.search);
    return;
  }
  ($('panel-cover') as HTMLImageElement).src = cover(g.slug);
  $('panel-name').textContent = g.name;
  $('panel-runtime').textContent = g.runtime;
  $('panel-lang').textContent = g.language;
  $('panel-tasks').innerHTML = `${g.tasks} <small>· ${g.repair} repair / ${g.construct} construction</small>`;
  $('panel-best').innerHTML = `${pct(g.best)} <small>· ${names(g.bestModels)}</small>`;
  $('panel-mean').textContent = pct(g.mean);
  const ranked = [...data.models].sort((a, b) => g.scores[b.slug].all - g.scores[a.slug].all);
  $('panel-bars').innerHTML = ranked.map((m) => `<li><span>${m.name}</span><div class="track"><div class="fill" style="width:0"></div></div><span class="v">${g.scores[m.slug].all.toFixed(1)}</span></li>`).join('');
  requestAnimationFrame(() => requestAnimationFrame(() => {
    $('panel-bars').querySelectorAll<HTMLElement>('.fill').forEach((f, i) => { f.style.width = `${g.scores[ranked[i].slug].all}%`; });
  }));
  $('readout-main').textContent = `${g.name} · ${g.tasks} tasks`;
  $('readout-sub').textContent = 'Esc or × to close';
  history.replaceState(null, '', `#game=${g.slug}`);
}

const globe = createGlobe({
  stage: $('globe-stage'),
  canvas: $('globe') as HTMLCanvasElement,
  labels: $('globe-labels'),
  games: games.map((g) => ({ slug: g.slug, name: g.name, sub: `${g.language} · ${g.tasks} tasks`, thumb: thumb(g.slug), repair: g.repair, construct: g.construct })),
  onSelect: show,
});
const choose = (slug: string | null) => { globe.select(slug); show(slug); };

$('panel-close').addEventListener('click', () => choose(null));
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && globe.selected) choose(null); });

// Covers: tilt toward the pointer, select on click, dim when filtered out by language.
const grid = $('game-grid');
const fine = matchMedia('(hover: hover) and (pointer: fine)');
const still = matchMedia('(prefers-reduced-motion: reduce)');
games.forEach((g, i) => {
  const b = document.createElement('button');
  b.type = 'button';
  b.className = 'cover';
  b.dataset.game = g.slug;
  b.dataset.lang = g.language;
  b.style.setProperty('--i', String(i));
  b.innerHTML = `<span class="cover-art"><img src="${cover(g.slug)}" alt="" width="360" height="540" loading="lazy" decoding="async" /><span class="cover-tag"></span></span>
    <span class="g-split" aria-hidden="true">${g.repair ? `<i class="r" style="flex:${g.repair}"></i>` : ''}${g.construct ? `<i class="c" style="flex:${g.construct}"></i>` : ''}</span>
    <span class="cover-meta"><b></b><span>${g.tasks} tasks<span class="m-best"> · best ${pct(g.best)}</span></span></span>`;
  b.querySelector('.cover-tag')!.textContent = g.language;
  b.querySelector('b')!.textContent = g.name;
  b.setAttribute('aria-label', `${g.name}: ${g.language}, ${g.runtime}, ${g.tasks} tasks (${g.repair} repair, ${g.construct} construction), best ${pct(g.best)}. Show on the globe.`);
  b.addEventListener('click', () => {
    choose(g.slug);
    $('top').scrollIntoView({ behavior: still.matches ? 'auto' : 'smooth' });
  });
  const art = b.querySelector<HTMLElement>('.cover-art')!;
  b.addEventListener('pointermove', (e) => {
    if (!fine.matches || still.matches) return;
    const r = art.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
    b.classList.add('tilt');
    b.style.setProperty('--ry', `${((x - 0.5) * 14).toFixed(2)}deg`);
    b.style.setProperty('--rx', `${((0.5 - y) * 14).toFixed(2)}deg`);
    b.style.setProperty('--mx', `${(x * 100).toFixed(1)}%`);
    b.style.setProperty('--my', `${(y * 100).toFixed(1)}%`);
  });
  b.addEventListener('pointerleave', () => {
    b.classList.remove('tilt');
    b.style.setProperty('--rx', '0deg');
    b.style.setProperty('--ry', '0deg');
  });
  grid.append(b);
});

const filter = $('lang-filter');
const fbtns = [...filter.querySelectorAll<HTMLButtonElement>('button')];
const pickLang = (btn: HTMLButtonElement) => {
  const lang = btn.dataset.lang!;
  fbtns.forEach((x) => { x.setAttribute('aria-selected', String(x === btn)); x.tabIndex = x === btn ? 0 : -1; });
  grid.querySelectorAll<HTMLElement>('.cover').forEach((c) => {
    const hit = !lang || c.dataset.lang!.split(/[\s·]+/).some((t) => t === lang || (lang === 'Lua' && t === 'GLua'));
    c.classList.toggle('dim', !hit);
  });
};
fbtns.forEach((btn, i) => {
  btn.tabIndex = i === 0 ? 0 : -1;
  btn.addEventListener('click', () => pickLang(btn));
  btn.addEventListener('keydown', (e) => {
    const d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
    if (!d) return;
    const n = fbtns[(i + d + fbtns.length) % fbtns.length];
    n.focus(); pickLang(n);
  });
});

// The scrolling strip of covers in the "why" section (two copies make the loop seamless).
const strip = $('why-strip');
strip.innerHTML = [...games, ...games].map((g) => `<img src="${cover(g.slug)}" alt="" width="56" height="84" loading="lazy" decoding="async" />`).join('');

// Candidate funnel bar
const T = data.totals as Record<string, number>;
document.querySelector<HTMLElement>('.sf-bar')?.style.setProperty('--keep', `${((T.tasks / T.candidates) * 100).toFixed(1)}%`);

// Abstract: four lines until opened
const absBtn = $('abs-more');
absBtn.addEventListener('click', () => {
  const open = absBtn.closest('.abstract')!.classList.toggle('open');
  absBtn.setAttribute('aria-expanded', String(open));
  absBtn.textContent = open ? 'Show less' : 'Read the full abstract';
});

const fromHash = () => {
  const m = /^#game=([a-z0-9-]+)$/.exec(location.hash);
  if (m && games.some((g) => g.slug === m[1])) choose(m[1]);
};
fromHash();
window.addEventListener('hashchange', fromHash);

initResults();
initExplainers();

/* Reveal sections and mark the current one in the nav */
const io = new IntersectionObserver((entries) => {
  for (const e of entries) if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
}, { rootMargin: '0px 0px -10% 0px', threshold: 0.08 });
document.querySelectorAll('.reveal').forEach((s) => io.observe(s));

const links = new Map([...document.querySelectorAll<HTMLAnchorElement>('.nav-links a')].map((a) => [a.hash.slice(1), a]));
const spy = new IntersectionObserver((entries) => {
  for (const e of entries) {
    if (!e.isIntersecting) continue;
    links.forEach((a, id) => a.classList.toggle('on', id === e.target.id));
    // the hero (#top) has no link, so reaching it clears the highlight
  }
}, { rootMargin: '-45% 0px -50% 0px' });
[...links.keys(), 'top'].forEach((id) => { const s = document.getElementById(id); if (s) spy.observe(s); });
