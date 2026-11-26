// Light/dark theme: a stored choice wins; without one the page follows the system setting.
const KEY = 'gameswe-theme';
const root = document.documentElement;

function stored(): string | null {
  try { return localStorage.getItem(KEY); } catch { return null; }
}

function apply(theme: 'light' | 'dark', save: boolean) {
  root.setAttribute('data-theme', theme);
  if (save) { try { localStorage.setItem(KEY, theme); } catch { /* private mode */ } }
  const btn = document.getElementById('theme-btn');
  btn?.setAttribute('aria-label', theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
  const bg = getComputedStyle(root).getPropertyValue('--bg').trim();
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', bg);
  window.dispatchEvent(new CustomEvent('themechange'));
}

export function initTheme() {
  const mq = matchMedia('(prefers-color-scheme: dark)');
  apply((stored() as 'light' | 'dark' | null) ?? (mq.matches ? 'dark' : 'light'), false);
  mq.addEventListener('change', (e) => { if (!stored()) apply(e.matches ? 'dark' : 'light', false); });
  document.getElementById('theme-btn')?.addEventListener('click', () => {
    apply(root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark', true);
  });
}
