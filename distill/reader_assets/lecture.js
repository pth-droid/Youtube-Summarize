/* Lecture deck controls. Slides are static HTML; this script only moves, fits and reveals them. */
(() => {
  'use strict';
  const root = document.documentElement;
  const frames = [...document.querySelectorAll('.slide-frame')];
  const deck = document.getElementById('deck'), counter = document.getElementById('counter');
  const bar = document.getElementById('progress-bar'), status = document.getElementById('deck-status');
  const outline = document.getElementById('outline'), notesToggle = document.getElementById('notes-toggle');
  const wide = matchMedia('screen and (min-width: 761px)');
  const presenting = () => root.classList.contains('js-deck') && wide.matches;
  const saved = {get(key) {try {return localStorage.getItem(key);} catch {return null;}}, set(key, value) {try {localStorage.setItem(key, value);} catch {}}};
  let current = 0;

  function fit() {
    if (!presenting()) return;
    const notes = document.body.classList.contains('show-notes') ? innerHeight * .28 + 12 : 0;
    const scale = Math.min((deck.clientWidth - 32) / 1280, (deck.clientHeight - 32 - notes) / 720);
    deck.style.setProperty('--scale', Math.max(.1, scale).toFixed(4));
  }
  // Shrink text that would overflow the fixed canvas instead of cutting it off.
  function tighten() {
    if (!presenting()) return;
    for (const slide of document.querySelectorAll('.slide')) {
      slide.classList.remove('dense', 'denser');
      for (const level of ['dense', 'denser']) {
        if (slide.scrollHeight <= slide.clientHeight + 1) break;
        slide.classList.remove('dense');
        slide.classList.add(level);
      }
    }
  }
  function show(index) {
    current = Math.max(0, Math.min(frames.length - 1, index));
    const hide = presenting();
    frames.forEach((frame, position) => {
      frame.classList.toggle('is-current', position === current);
      frame.inert = hide && position !== current;
    });
    counter.textContent = `${current + 1} / ${frames.length}`;
    bar.style.width = `${(current + 1) / frames.length * 100}%`;
    status.textContent = hide ? frames[current].getAttribute('aria-label') : '';
    // Stacked reading mode keeps the address unchanged; the browser would scroll to the fragment.
    if (hide) try { history.replaceState(null, '', `#slide-${current + 1}`); } catch {}
    fit();
  }
  function setNotes(visible) {
    document.body.classList.toggle('show-notes', visible);
    notesToggle.setAttribute('aria-pressed', String(visible));
    saved.set('distill-lecture-notes', visible ? '1' : '0');
    fit();
  }
  function fullscreen() {
    if (!document.fullscreenEnabled) return;
    if (document.fullscreenElement) document.exitFullscreen(); else root.requestFullscreen().catch(() => {});
  }
  function reveal(slide) {
    slide.classList.add('revealed');
    slide.querySelectorAll('.option[data-correct="true"]').forEach(option => option.classList.add('right'));
  }

  document.getElementById('prev').addEventListener('click', () => show(current - 1));
  document.getElementById('next').addEventListener('click', () => show(current + 1));
  notesToggle.addEventListener('click', () => setNotes(!document.body.classList.contains('show-notes')));
  document.getElementById('print-button').addEventListener('click', () => window.print());
  const full = document.getElementById('fullscreen-button');
  full.hidden = !document.fullscreenEnabled;
  full.addEventListener('click', fullscreen);
  document.getElementById('outline-button').addEventListener('click', () => {
    outline.querySelectorAll('li').forEach((item, position) => item.classList.toggle('current', position === current));
    outline.showModal();
    outline.querySelector('.current button')?.focus();
  });
  outline.addEventListener('click', event => {
    const target = event.target.closest('[data-go]');
    if (!target) return;
    outline.close();
    show(Number(target.dataset.go) - 1);
    if (!presenting()) frames[current].scrollIntoView({block: 'start'});
  });
  deck.addEventListener('click', event => {
    const option = event.target.closest('.option'), button = event.target.closest('.reveal');
    if (option) {
      if (option.dataset.correct !== 'true') option.classList.add('wrong');
      reveal(option.closest('.slide'));
    } else if (button) reveal(button.closest('.slide'));
  });
  document.addEventListener('keydown', event => {
    if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || outline.open) return;
    // A figure's scrubber and other fields keep their own arrow keys.
    if (event.target.closest?.('input, textarea, select')) return;
    const key = event.key.length === 1 ? event.key.toLowerCase() : event.key;
    if (key === 'n') return setNotes(!document.body.classList.contains('show-notes'));
    if (!presenting()) return;
    const control = event.target.closest?.('button, a, input, textarea, select');
    const step = {ArrowRight: 1, ArrowDown: 1, PageDown: 1, ArrowLeft: -1, ArrowUp: -1, PageUp: -1}[key] ?? (key === ' ' && !control ? (event.shiftKey ? -1 : 1) : 0);
    if (step) show(current + step);
    else if (key === 'Home') show(0);
    else if (key === 'End') show(frames.length - 1);
    else if (key === 'f') fullscreen();
    else return;
    event.preventDefault();
  });
  let touchStart = null;
  deck.addEventListener('pointerdown', event => { if (event.pointerType !== 'mouse') touchStart = event.clientX; });
  deck.addEventListener('pointerup', event => {
    if (touchStart === null || !presenting()) return;
    const distance = event.clientX - touchStart;
    touchStart = null;
    if (Math.abs(distance) > 60) show(current + (distance < 0 ? 1 : -1));
  });
  addEventListener('resize', fit);
  wide.addEventListener('change', () => { tighten(); show(current); });
  document.addEventListener('fullscreenchange', fit);

  const linked = () => Number((location.hash.match(/^#slide-(\d+)$/) || [])[1]) - 1;
  addEventListener('hashchange', () => { if (linked() >= 0 && linked() !== current) show(linked()); });
  setNotes(saved.get('distill-lecture-notes') === '1');
  tighten();
  show(linked() >= 0 ? linked() : 0);
  document.fonts?.ready.then(() => { tighten(); fit(); });
})();
