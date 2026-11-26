import './style.css';
import { data, modelBySlug, pct } from './data';
import { initTheme } from './theme';
import { createGlobe } from './globe';
import { initResults } from './results';

document.documentElement.classList.add('js');
initTheme();

// Fill every [data-bind] from data.json, so the page has one source for its numbers.
const lookup = (path: string): unknown => path.split('.').reduce<unknown>((o, k) => (o as Record<string, unknown>)?.[k], data);
document.querySelectorAll<HTMLElement>('[data-bind]').forEach((n) => {
  const v = lookup(n.dataset.bind!);
  let s = String(v);
  if (typeof v === 'number') {
    if (n.dataset.fmt === 'pct') s = pct(v);
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

function show(slug: string | null) {
  const g = games.find((x) => x.slug === slug);
  hero.classList.toggle('has-game', !!g);
  panel.hidden = !g;
  document.querySelectorAll('.g-tile').forEach((t) => t.classList.toggle('on', (t as HTMLElement).dataset.game === slug));
  if (!g) {
    $('readout-main').textContent = 'Select a game';
    $('readout-sub').textContent = 'Click a label · drag to explore';
    history.replaceState(null, '', location.pathname + location.search);
    return;
  }
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
  games: games.map((g) => ({ slug: g.slug, name: g.name, sub: `${g.language} · ${g.tasks} tasks`, repair: g.repair, construct: g.construct })),
  onSelect: show,
});
const choose = (slug: string | null) => { globe.select(slug); show(slug); };

$('panel-close').addEventListener('click', () => choose(null));
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && globe.selected) choose(null); });

const grid = $('game-grid');
for (const g of games) {
  const b = document.createElement('button');
  b.type = 'button';
  b.className = 'g-tile';
  b.dataset.game = g.slug;
  b.innerHTML = `<span class="g-chip"></span><h3></h3><span class="g-rt"></span>
    <span class="g-foot"><span><b>${g.tasks}</b> tasks</span><span>best <b>${pct(g.best)}</b></span></span>
    <span class="g-split" aria-hidden="true">${g.repair ? `<i class="r" style="flex:${g.repair}"></i>` : ''}${g.construct ? `<i class="c" style="flex:${g.construct}"></i>` : ''}</span>`;
  b.querySelector('.g-chip')!.textContent = g.language;
  b.querySelector('h3')!.textContent = g.name;
  b.querySelector('.g-rt')!.textContent = g.runtime;
  b.setAttribute('aria-label', `${g.name}: ${g.language}, ${g.runtime}, ${g.tasks} tasks (${g.repair} repair, ${g.construct} construction), best ${pct(g.best)}. Show on the globe.`);
  b.addEventListener('click', () => {
    choose(g.slug);
    $('top').scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
  });
  grid.append(b);
}

const fromHash = () => {
  const m = /^#game=([a-z0-9-]+)$/.exec(location.hash);
  if (m && games.some((g) => g.slug === m[1])) choose(m[1]);
};
fromHash();
window.addEventListener('hashchange', fromHash);

initResults();

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
