// Results section: leaderboard with metric tabs, per-game heatmap, stage bar and attempt funnel.
import { data, icon, pct, type Model } from './data';

type Metric = 'overall' | 'repair' | 'construct';
type Kind = 'all' | 'rep' | 'con';

const T = data.totals as Record<string, number>;
const DESC: Record<Metric, string> = {
  overall: `Average of the ${T.games} per-game resolution rates; each game counts equally.`,
  repair: `Pooled over the ${T.repair} repair tasks.`,
  construct: `Pooled over the ${T.construct} construction tasks.`,
};
const METRIC_NAME: Record<Metric, string> = { overall: 'Overall', repair: 'Repair', construct: 'Construction' };
const FUNNEL: [keyof Model['funnel'], string][] = [
  ['changed', 'Changed the code'], ['reachedTests', 'Reached the tests'], ['f2p', 'Passed all F2P'],
  ['f2pAndP2p', 'Passed F2P and P2P'], ['resolved', 'Resolved'],
];

const el = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const reduced = matchMedia('(prefers-reduced-motion: reduce)');

// One floating tooltip shared by every chart.
const tip = document.createElement('div');
tip.className = 'tip';
tip.setAttribute('role', 'tooltip');
document.body.append(tip);
function showTip(html: string, e: MouseEvent) {
  tip.innerHTML = html;
  tip.classList.add('show');
  const w = tip.offsetWidth, h = tip.offsetHeight;
  let x = e.clientX + 14, y = e.clientY + 16;
  if (x + w > innerWidth - 8) x = e.clientX - w - 14;
  if (y + h > innerHeight - 8) y = e.clientY - h - 12;
  tip.style.transform = `translate(${x}px, ${y}px)`;
}
const hideTip = () => tip.classList.remove('show');
const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]!);

function tabs(root: HTMLElement, attr: string, onPick: (v: string) => void) {
  const btns = [...root.querySelectorAll<HTMLButtonElement>('button')];
  const pick = (b: HTMLButtonElement) => {
    btns.forEach((x) => { x.setAttribute('aria-selected', String(x === b)); x.tabIndex = x === b ? 0 : -1; });
    onPick(b.dataset[attr]!);
  };
  btns.forEach((b, i) => {
    b.tabIndex = i === 0 ? 0 : -1;
    b.addEventListener('click', () => pick(b));
    b.addEventListener('keydown', (e) => {
      const d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
      if (!d) return;
      const n = btns[(i + d + btns.length) % btns.length];
      n.focus(); pick(n);
    });
  });
}

/* Leaderboard */
function initBoard() {
  const list = el('board-rows');
  const rows = new Map<string, HTMLLIElement>();
  for (const m of data.models) {
    const li = document.createElement('li');
    li.className = 'b-row';
    li.innerHTML = `<div class="b-who"><span class="b-rank"></span><span class="b-icon"><img alt="" src="${icon(m)}" width="15" height="15" /></span><span class="b-name"></span></div><div class="b-track"><div class="b-bar"></div></div><span class="b-val"></span>`;
    li.querySelector('.b-name')!.textContent = m.name;
    rows.set(m.slug, li);
    list.append(li);
  }
  let metric: Metric = 'overall';
  const counts = (m: Model): string => {
    if (metric === 'overall') return `${m.resolved} of ${T.tasks} tasks resolved`;
    if (metric === 'repair') return `${Math.round((m.repair * T.repair) / 100)} of ${T.repair} repair tasks`;
    return `${Math.round((m.construct * T.construct) / 100)} of ${T.construct} construction tasks`;
  };
  for (const m of data.models) {
    const li = rows.get(m.slug)!;
    li.addEventListener('mousemove', (e) => showTip(`<b>${esc(m.name)}</b>${METRIC_NAME[metric]} <span>${pct(m[metric])}</span><br>${counts(m)}`, e));
    li.addEventListener('mouseleave', hideTip);
  }

  const render = (first = false) => {
    el('board-desc').textContent = DESC[metric];
    const order = [...data.models].sort((a, b) => b[metric] - a[metric] || b.overall - a.overall);
    const before = new Map([...rows].map(([k, r]) => [k, r.offsetTop]));
    order.forEach((m, i) => {
      const r = rows.get(m.slug)!;
      list.append(r);
      r.querySelector('.b-rank')!.textContent = String(i + 1);
      r.querySelector<HTMLElement>('.b-val')!.textContent = pct(m[metric]);
      r.querySelector<HTMLElement>('.b-bar')!.style.width = first ? '0%' : `${m[metric]}%`;
      r.setAttribute('aria-label', `${i + 1}. ${m.name}: ${pct(m[metric])}`);
    });
    if (first || reduced.matches) return;
    // FLIP: slide each row from its old position to the new one.
    for (const [k, r] of rows) {
      const d = before.get(k)! - r.offsetTop;
      if (!d) continue;
      r.animate([{ transform: `translateY(${d}px)` }, { transform: 'none' }], { duration: 520, easing: 'cubic-bezier(.2,.8,.2,1)' });
    }
  };
  render(true);
  // Grow the bars once the board scrolls into view.
  new IntersectionObserver(([e], o) => {
    if (!e.isIntersecting) return;
    o.disconnect();
    for (const m of data.models) rows.get(m.slug)!.querySelector<HTMLElement>('.b-bar')!.style.width = `${m[metric]}%`;
  }, { threshold: 0.3 }).observe(list);
  tabs(el('board-tabs'), 'metric', (v) => { metric = v as Metric; render(); });
}

/* Heatmap */
function initHeat() {
  const table = el<HTMLTableElement>('heat-table');
  const games = data.games;
  const head = `<thead><tr><th scope="col"><span class="sr">Model</span></th>${games.map((g, i) => `<th scope="col" data-col="${i}">${esc(g.name)}</th>`).join('')}<th class="gap" aria-hidden="true"></th><th scope="col" class="tot" data-col="t">Total</th></tr></thead>`;
  const body = data.models.map((m) => `<tr data-model="${m.slug}"><th scope="row"><span><span class="h-icon"><img alt="" src="${icon(m)}" width="12" height="12" /></span>${esc(m.name)}</span></th>${games.map((_, i) => `<td data-col="${i}"></td>`).join('')}<td class="gap" aria-hidden="true"></td><td class="tot" data-col="t"></td></tr>`).join('');
  table.innerHTML = `${head}<tbody>${body}</tbody>`;
  let kind: Kind = 'all';
  const total = (m: Model) => (kind === 'all' ? m.overall : kind === 'rep' ? m.repair : m.construct);
  const paint = (td: HTMLElement, v: number | null) => {
    td.classList.toggle('na', v === null);
    td.classList.toggle('hi', v !== null && v >= 55);
    td.textContent = v === null ? '–' : v.toFixed(1);
    td.style.background = v === null ? '' : `color-mix(in oklab, var(--seq-hi) ${v}%, var(--seq-lo))`;
  };
  const render = () => {
    for (const m of data.models) {
      const tr = table.querySelector(`tr[data-model="${m.slug}"]`)!;
      games.forEach((g, i) => paint(tr.querySelector(`td[data-col="${i}"]`)!, g.scores[m.slug][kind]));
      paint(tr.querySelector('td.tot')!, total(m));
    }
  };
  render();
  tabs(el('heat-tabs'), 'kind', (v) => { kind = v as Kind; render(); });

  const heads = [...table.querySelectorAll<HTMLElement>('thead th[data-col]')];
  table.addEventListener('mouseover', (e) => {
    const td = (e.target as HTMLElement).closest('td');
    if (!td || td.classList.contains('gap')) return;
    const col = td.dataset.col!;
    table.querySelectorAll('tr.on').forEach((r) => r.classList.remove('on'));
    td.parentElement!.classList.add('on');
    heads.forEach((h) => h.classList.toggle('on', h.dataset.col === col));
  });
  table.addEventListener('mousemove', (e) => {
    const td = (e.target as HTMLElement).closest('td');
    if (!td || td.classList.contains('gap')) return hideTip();
    const m = data.models.find((x) => x.slug === td.parentElement!.dataset.model)!;
    const col = td.dataset.col!;
    if (col === 't') {
      return showTip(`<b>${esc(m.name)} · Total</b>All <span>${pct(m.overall)}</span> · Repair <span>${pct(m.repair)}</span> · Construction <span>${pct(m.construct)}</span>`, e);
    }
    const g = games[+col];
    const c = g.scores[m.slug];
    const part = (label: string, v: number | null) => `${label} <span>${v === null ? '–' : pct(v)}</span>`;
    showTip(`<b>${esc(m.name)} · ${esc(g.name)}</b>${part('All', c.all)} · ${part('Repair', c.rep)} · ${part('Construction', c.con)}<br>${g.tasks} tasks: ${g.repair} repair, ${g.construct} construction`, e);
  });
  table.addEventListener('mouseleave', () => {
    hideTip();
    table.querySelectorAll('.on').forEach((x) => x.classList.remove('on'));
  });
}

/* Where unresolved attempts stop */
function initStages() {
  const f = data.findings;
  const bar = el('stage-bar');
  const legend = el('stage-legend');
  bar.innerHTML = f.stages.map((s, i) => {
    const share = (s.n / f.unresolved) * 100;
    return `<i class="s${i + 1}" style="flex:${s.n} 1 0">${share >= 9 ? s.n : ''}</i>`;
  }).join('');
  bar.setAttribute('aria-label', `Unresolved attempts by stage: ${f.stages.map((s) => `${s.label} ${s.n}`).join(', ')}`);
  legend.innerHTML = f.stages.map((s, i) => `<li><b class="s${i + 1}"></b><span>${esc(s.label)}</span><span class="n">${s.n}</span><span class="p">${pct((s.n / f.unresolved) * 100)}</span></li>`).join('');
  [...bar.children].forEach((seg, i) => {
    const s = f.stages[i];
    seg.addEventListener('mousemove', (e) => showTip(`<b>${esc(s.label)}</b><span>${s.n}</span> of ${f.unresolved} unresolved attempts (${pct((s.n / f.unresolved) * 100)})`, e as MouseEvent));
    seg.addEventListener('mouseleave', hideTip);
  });
}

/* Funnel */
function initFunnel() {
  const sel = el<HTMLSelectElement>('funnel-model');
  sel.innerHTML = data.models.map((m) => `<option value="${m.slug}">${esc(m.name)}</option>`).join('');
  const list = el('funnel-rows');
  list.innerHTML = FUNNEL.map(([k, label]) => `<li data-k="${k}"><span>${label}</span><div class="track"><div class="fill"></div></div><span class="v"></span></li>`).join('');
  const render = () => {
    const m = data.models.find((x) => x.slug === sel.value)!;
    for (const [k] of FUNNEL) {
      const li = list.querySelector<HTMLElement>(`li[data-k="${k}"]`)!;
      li.querySelector<HTMLElement>('.fill')!.style.width = `${m.funnel[k]}%`;
      li.querySelector('.v')!.textContent = pct(m.funnel[k]);
    }
  };
  sel.addEventListener('change', render);
  render();
}

export function initResults() {
  initBoard();
  initHeat();
  initStages();
  initFunnel();
}
