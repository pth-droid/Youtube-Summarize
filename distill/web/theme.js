/* Shared by the workspace and portable learning pages. Saved pages embed a copy,
   so the pre-rename storage key and message types must stay unchanged. */
(() => {
  'use strict';
  const key = 'visual-learning-theme';
  const valid = value => value === 'light' || value === 'dark';
  let theme = 'dark';
  try { const saved = localStorage.getItem(key); if (valid(saved)) theme = saved; } catch {}
  function apply(value, save = false) {
    if (!valid(value)) return;
    theme = value;
    document.documentElement.dataset.theme = value;
    document.documentElement.style.colorScheme = value;
    if (save) { try { localStorage.setItem(key, value); } catch {} }
    const toggle = document.getElementById('theme-toggle');
    if (toggle) {
      const vi = document.documentElement.lang === 'vi';
      toggle.textContent = value === 'dark' ? (vi ? 'Chế độ sáng' : 'Light mode') : (vi ? 'Chế độ tối' : 'Dark mode');
      toggle.setAttribute('aria-label', value === 'dark' ? (vi ? 'Chuyển sang chế độ sáng' : 'Switch to light mode') : (vi ? 'Chuyển sang chế độ tối' : 'Switch to dark mode'));
    }
    const frame = document.getElementById('reader-frame');
    if (frame?.contentWindow) frame.contentWindow.postMessage({type:'visual-learning-theme', theme:value}, '*');
  }
  apply(theme);
  window.addEventListener('message', event => {
    const frame = document.getElementById('reader-frame');
    if (frame && event.source === frame.contentWindow) {
      if (event.data?.type === 'visual-learning-theme-request') apply(theme);
      if (event.data?.type === 'visual-learning-theme-change' && valid(event.data.theme)) apply(event.data.theme, true);
    } else if (window.parent !== window && event.source === window.parent && event.data?.type === 'visual-learning-theme') {
      apply(event.data.theme);
    }
  });
  window.addEventListener('storage', event => { if (event.key === key) apply(valid(event.newValue) ? event.newValue : 'dark'); });
  document.addEventListener('DOMContentLoaded', () => {
    apply(theme);
    document.getElementById('theme-toggle')?.addEventListener('click', () => {
      apply(theme === 'dark' ? 'light' : 'dark', true);
      if (window.parent !== window) window.parent.postMessage({type:'visual-learning-theme-change', theme}, '*');
    });
    document.getElementById('reader-frame')?.addEventListener('load', () => apply(theme));
    if (window.parent !== window) window.parent.postMessage({type:'visual-learning-theme-request'}, '*');
  });
})();
