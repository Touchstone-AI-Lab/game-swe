// A draggable dotted globe drawn on a 2D canvas. Every task is one dot, clustered by game:
// repair tasks are filled, construction tasks are rings. Game labels are HTML buttons placed over the
// canvas each frame and faded out as their cluster turns away.

export interface GlobeGame { slug: string; name: string; sub: string; thumb: string; repair: number; construct: number }

interface Vec { x: number; y: number; z: number }
interface Task { p: Vec; game: number; construct: boolean }

const TAU = Math.PI * 2;
const GOLDEN = Math.PI * (3 - Math.sqrt(5));
const STEP = 0.047; // spacing of task dots inside a cluster, in radians
const LATS = [26, -18, 40, -34, 12, -42, 32, -6, 46, -28, 16, -40];
const reduced = matchMedia('(prefers-reduced-motion: reduce)');

const fromLatLon = (lat: number, lon: number): Vec => ({
  x: Math.cos(lat) * Math.sin(lon), y: Math.sin(lat), z: Math.cos(lat) * Math.cos(lon),
});
const norm = (v: Vec): Vec => { const l = Math.hypot(v.x, v.y, v.z); return { x: v.x / l, y: v.y / l, z: v.z / l }; };
const cross = (a: Vec, b: Vec): Vec => ({ x: a.y * b.z - a.z * b.y, y: a.z * b.x - a.x * b.z, z: a.x * b.y - a.y * b.x });
const dot = (a: Vec, b: Vec) => a.x * b.x + a.y * b.y + a.z * b.z;
const wrap = (a: number) => Math.atan2(Math.sin(a), Math.cos(a));
const smooth = (a: number, b: number, x: number) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };

export function createGlobe(opts: {
  stage: HTMLElement; canvas: HTMLCanvasElement; labels: HTMLElement; games: GlobeGame[];
  onSelect: (slug: string | null) => void;
}) {
  const { stage, canvas, labels, games, onSelect } = opts;
  const ctx = canvas.getContext('2d')!;

  // Cluster centres: twelve evenly spaced longitudes, latitudes alternating north and south.
  const centers = games.map((_, i) => fromLatLon((LATS[i % LATS.length] * Math.PI) / 180, (i / games.length) * TAU));
  const lonOf = games.map((_, i) => (i / games.length) * TAU);
  const latOf = games.map((_, i) => (LATS[i % LATS.length] * Math.PI) / 180);
  const radius: number[] = [];
  const tasks: Task[] = [];
  games.forEach((g, gi) => {
    const c = centers[gi];
    const east = norm(cross({ x: 0, y: 1, z: 0 }, c));
    const north = cross(c, east);
    const n = g.repair + g.construct;
    for (let k = 0; k < n; k++) {
      const r = STEP * Math.sqrt(k + 0.5);
      const a = k * GOLDEN;
      const p = norm({
        x: c.x + east.x * r * Math.cos(a) + north.x * r * Math.sin(a),
        y: c.y + east.y * r * Math.cos(a) + north.y * r * Math.sin(a),
        z: c.z + east.z * r * Math.cos(a) + north.z * r * Math.sin(a),
      });
      tasks.push({ p, game: gi, construct: k >= g.repair }); // repairs in the core, constructions around them
    }
    radius.push(STEP * Math.sqrt(n));
  });

  // Background: a Fibonacci sphere, thinned where the clusters sit.
  const field: Vec[] = [];
  const N = 1500;
  for (let i = 0; i < N; i++) {
    const y = 1 - (2 * (i + 0.5)) / N;
    const r = Math.sqrt(1 - y * y);
    const p = { x: Math.cos(i * GOLDEN) * r, y, z: Math.sin(i * GOLDEN) * r };
    if (centers.some((c, gi) => Math.acos(Math.min(1, dot(p, c))) < radius[gi] + 0.05)) continue;
    field.push(p);
  }

  // Labels
  const buttons = games.map((g, gi) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'g-label';
    b.dataset.game = g.slug;
    b.setAttribute('aria-pressed', 'false');
    b.innerHTML = `<img alt="" width="16" height="24" /><span class="gl-t"><strong></strong><span></span></span>`;
    b.querySelector('img')!.src = g.thumb;
    b.querySelector('strong')!.textContent = g.name;
    b.querySelector('.gl-t > span')!.textContent = g.sub;
    b.addEventListener('click', () => select(selected === gi ? null : g.slug));
    b.addEventListener('focus', () => { if (selected < 0) aim(gi); });
    labels.append(b);
    return b;
  });

  let yaw = -0.35, pitch = 0.3, vy = 0, vp = 0;
  let target: { yaw: number; pitch: number } | null = null;
  let selected = -1;
  let colors = readColors();
  let size = 0, dpr = 1;
  let visible = true, dirty = true, last = performance.now();
  let drag: { x: number; y: number; moved: number; t: number } | null = null;
  let hover = false; // auto-rotation pauses while the pointer is over the globe, so labels hold still

  function readColors() {
    const s = getComputedStyle(document.documentElement);
    const v = (n: string) => s.getPropertyValue(n).trim();
    return { fg: v('--fg'), bg: v('--bg'), rep: v('--rep'), con: v('--con'), accent: v('--accent'), dark: document.documentElement.dataset.theme === 'dark' };
  }

  function resize() {
    dpr = Math.min(2, window.devicePixelRatio || 1);
    size = canvas.clientWidth;
    canvas.width = Math.round(size * dpr);
    canvas.height = Math.round(size * dpr);
    dirty = true;
  }

  function project(p: Vec) {
    const cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
    const x1 = p.x * cy + p.z * sy;
    const z1 = -p.x * sy + p.z * cy;
    const y2 = p.y * cp - z1 * sp;
    const z2 = p.y * sp + z1 * cp;
    return { x: x1, y: y2, z: z2 };
  }

  function aim(gi: number) {
    target = { yaw: yaw + wrap(-lonOf[gi] - yaw), pitch: Math.max(-0.7, Math.min(0.7, latOf[gi])) };
    if (reduced.matches) { yaw = target.yaw; pitch = target.pitch; target = null; }
    dirty = true;
  }

  function select(slug: string | null, notify = true) {
    const gi = slug ? games.findIndex((g) => g.slug === slug) : -1;
    selected = gi;
    buttons.forEach((b, i) => { b.classList.toggle('on', i === gi); b.setAttribute('aria-pressed', String(i === gi)); });
    if (gi >= 0) aim(gi);
    dirty = true;
    if (notify) onSelect(gi >= 0 ? games[gi].slug : null);
  }

  function draw() {
    const R = size * 0.43;
    const cx = size / 2, cy = size / 2;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, size, size);

    // Body and rim
    const body = ctx.createRadialGradient(cx - R * 0.35, cy - R * 0.4, R * 0.1, cx, cy, R);
    body.addColorStop(0, colors.dark ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.9)');
    body.addColorStop(1, colors.dark ? 'rgba(255,255,255,0.012)' : 'rgba(255,255,255,0.25)');
    ctx.fillStyle = body;
    ctx.beginPath(); ctx.arc(cx, cy, R, 0, TAU); ctx.fill();
    const rim = ctx.createRadialGradient(cx, cy, R * 0.86, cx, cy, R * 1.12);
    rim.addColorStop(0, 'rgba(0,0,0,0)');
    rim.addColorStop(0.55, hexA(colors.accent, colors.dark ? 0.16 : 0.12));
    rim.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = rim;
    ctx.beginPath(); ctx.arc(cx, cy, R * 1.12, 0, TAU); ctx.fill();

    // Field dots, front hemisphere only
    ctx.fillStyle = colors.fg;
    for (const p of field) {
      const q = project(p);
      if (q.z <= 0.02) continue;
      ctx.globalAlpha = (colors.dark ? 0.1 : 0.12) + q.z * (colors.dark ? 0.32 : 0.34);
      const r = 0.55 + q.z * 0.65;
      ctx.beginPath(); ctx.arc(cx + q.x * R, cy - q.y * R, r, 0, TAU); ctx.fill();
    }
    ctx.globalAlpha = 1;

    // Glow under the selected cluster
    if (selected >= 0) {
      const q = project(centers[selected]);
      if (q.z > 0) {
        const gx = cx + q.x * R, gy = cy - q.y * R, gr = radius[selected] * R * 2.2;
        const glow = ctx.createRadialGradient(gx, gy, 0, gx, gy, gr);
        glow.addColorStop(0, hexA(colors.accent, 0.22));
        glow.addColorStop(1, hexA(colors.accent, 0));
        ctx.fillStyle = glow;
        ctx.beginPath(); ctx.arc(gx, gy, gr, 0, TAU); ctx.fill();
      }
    }

    // Task dots: a surface-coloured ring keeps neighbours apart
    for (const t of tasks) {
      const q = project(t.p);
      if (q.z <= 0) continue;
      const on = selected < 0 || selected === t.game;
      const r = (2.3 + q.z * 1.2) * (selected === t.game ? 1.3 : 1);
      const x = cx + q.x * R, y = cy - q.y * R;
      ctx.globalAlpha = (on ? 1 : 0.28) * (0.35 + 0.65 * smooth(0, 0.35, q.z));
      ctx.fillStyle = colors.bg;
      ctx.beginPath(); ctx.arc(x, y, r + 1.6, 0, TAU); ctx.fill();
      if (t.construct) {
        ctx.strokeStyle = colors.con; ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.arc(x, y, r - 0.4, 0, TAU); ctx.stroke();
      } else {
        ctx.fillStyle = colors.rep;
        ctx.beginPath(); ctx.arc(x, y, r, 0, TAU); ctx.fill();
      }
    }
    ctx.globalAlpha = 1;

    // Labels above their clusters
    games.forEach((_, gi) => {
      const q = project(centers[gi]);
      const b = buttons[gi];
      const o = gi === selected ? Math.max(0.0, smooth(-0.05, 0.25, q.z)) : smooth(0.12, 0.42, q.z);
      const lift = radius[gi] * R * Math.max(0.3, q.z) + 10;
      const x = cx + q.x * R, y = cy - q.y * R - lift; // labels share the canvas box
      b.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px) translate(-50%, -100%) scale(${(0.92 + 0.08 * o).toFixed(3)})`;
      b.style.opacity = o.toFixed(3);
      b.classList.toggle('off', o < 0.3);
    });
  }

  function frame(now: number) {
    requestAnimationFrame(frame);
    const dt = Math.min(64, now - last);
    last = now;
    if (!visible || document.hidden) return;
    if (target) {
      const k = 1 - Math.pow(0.0035, dt / 1000);
      yaw += (target.yaw - yaw) * k;
      pitch += (target.pitch - pitch) * k;
      if (Math.abs(target.yaw - yaw) < 1e-3 && Math.abs(target.pitch - pitch) < 1e-3) target = null;
      dirty = true;
    } else if (!drag && !reduced.matches) {
      if (Math.abs(vy) > 1e-5 || Math.abs(vp) > 1e-5) {
        yaw += vy * dt; pitch = clampPitch(pitch + vp * dt);
        const f = Math.pow(0.04, dt / 1000);
        vy *= f; vp *= f;
        dirty = true;
      }
      if (selected < 0 && !hover) { yaw += 0.00007 * dt; dirty = true; }
    }
    if (dirty) { draw(); dirty = false; }
  }

  const clampPitch = (p: number) => Math.max(-0.9, Math.min(0.9, p));

  canvas.addEventListener('pointerdown', (e) => {
    drag = { x: e.clientX, y: e.clientY, moved: 0, t: performance.now() };
    target = null; vy = 0; vp = 0;
    canvas.setPointerCapture(e.pointerId);
    canvas.classList.add('dragging');
  });
  canvas.addEventListener('pointermove', (e) => {
    if (!drag) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    const now = performance.now();
    const dt = Math.max(1, now - drag.t);
    drag.moved += Math.abs(dx) + Math.abs(dy);
    drag.x = e.clientX; drag.y = e.clientY; drag.t = now;
    const k = 3.2 / size;
    yaw += dx * k; pitch = clampPitch(pitch + dy * k);
    vy = (dx * k) / dt; vp = (dy * k) / dt;
    dirty = true;
  });
  const end = (e: PointerEvent) => {
    if (!drag) return;
    const click = drag.moved < 5;
    drag = null;
    canvas.classList.remove('dragging');
    if (click && e.type === 'pointerup') { vy = 0; vp = 0; pick(e); }
  };
  canvas.addEventListener('pointerup', end);
  canvas.addEventListener('pointercancel', end);

  // A click on the globe selects the nearest visible cluster under the pointer.
  function pick(e: PointerEvent) {
    const rect = canvas.getBoundingClientRect();
    const R = size * 0.43;
    const px = e.clientX - rect.left - size / 2, py = e.clientY - rect.top - size / 2;
    let best = -1, bestD = Infinity;
    games.forEach((_, gi) => {
      const q = project(centers[gi]);
      if (q.z <= 0.1) return;
      const d = Math.hypot(q.x * R - px, -q.y * R - py);
      if (d < radius[gi] * R + 18 && d < bestD) { best = gi; bestD = d; }
    });
    if (best >= 0) select(best === selected ? null : games[best].slug);
  }

  stage.addEventListener('pointerenter', (e) => { if (e.pointerType === 'mouse') hover = true; });
  stage.addEventListener('pointerleave', () => { hover = false; });
  new ResizeObserver(resize).observe(canvas);
  new IntersectionObserver(([en]) => { visible = en.isIntersecting; if (visible) dirty = true; }).observe(stage);
  window.addEventListener('themechange', () => { colors = readColors(); dirty = true; });
  resize();
  requestAnimationFrame(frame);

  return { select: (slug: string | null) => select(slug, false), get selected() { return selected >= 0 ? games[selected].slug : null; } };
}

function hexA(color: string, a: number) {
  const m = /^#([0-9a-f]{6})$/i.exec(color);
  if (!m) return color;
  const n = parseInt(m[1], 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}
