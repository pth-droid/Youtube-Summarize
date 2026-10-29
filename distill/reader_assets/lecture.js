/* Lecture deck controls. Slides are static HTML; this script only moves, fits and builds them. */
(() => {
  'use strict';
  const root = document.documentElement;
  const frames = [...document.querySelectorAll('.slide-frame')];
  const deck = document.getElementById('deck'), counter = document.getElementById('counter');
  const bar = document.getElementById('progress-bar'), status = document.getElementById('deck-status');
  const outline = document.getElementById('outline'), notesToggle = document.getElementById('notes-toggle');
  const wide = matchMedia('screen and (min-width: 761px)');
  // A phone copy always presents and never shows notes: a mirrored phone puts everything on the room's TV.
  const phone = root.dataset.mode === 'phone';
  const presenting = () => root.classList.contains('js-deck') && (phone || wide.matches);
  const saved = {get(key) {try {return localStorage.getItem(key);} catch {return null;}}, set(key, value) {try {localStorage.setItem(key, value);} catch {}}};
  // Build steps: the renderer marks them with data-build. The first item of a list arrives with the slide;
  // each advance reveals the next marked item.
  const builds = frames.map(frame => [...frame.querySelectorAll('[data-build]')]);
  let current = 0, shown = 0;

  function fit() {
    if (!presenting()) return;
    const notes = document.body.classList.contains('show-notes') ? innerHeight * .28 + 12 : 0, margin = phone ? 0 : 32;
    const scale = Math.min((deck.clientWidth - margin) / 1280, (deck.clientHeight - margin - notes) / 720);
    deck.style.setProperty('--scale', Math.max(.1, scale).toFixed(4));
  }
  // Shrink text that would overflow the fixed canvas instead of cutting it off. Measured with motion off:
  // a part still rising into place is translated down and would count as overflow.
  function tighten() {
    if (!presenting()) return;
    root.classList.add('fitting');
    for (const slide of document.querySelectorAll('.slide')) {
      slide.classList.remove('dense', 'denser');
      for (const level of ['dense', 'denser']) {
        if (slide.scrollHeight <= slide.clientHeight + 1) break;
        slide.classList.remove('dense');
        slide.classList.add(level);
      }
    }
    root.classList.remove('fitting');
  }
  // Arriving forwards shows the first build item; arriving backwards shows the slide fully built.
  // The arrival names the motion: forward staggers in, back fades once, instant lands with none.
  function show(index, built = false, arrival = built ? 'back' : 'forward') {
    current = Math.max(0, Math.min(frames.length - 1, index));
    shown = built ? builds[current].length : 0;
    builds.flat().forEach(item => item.classList.remove('build-pending', 'build-shown'));
    builds[current].forEach((item, position) => item.classList.toggle('build-pending', position >= shown));
    const hide = presenting();
    frames.forEach((frame, position) => {
      frame.classList.toggle('is-current', position === current);
      frame.inert = hide && position !== current;
      if (position === current) frame.dataset.arrival = arrival; else delete frame.dataset.arrival;
    });
    counter.textContent = `${current + 1} / ${frames.length}`;
    bar.style.transform = `scaleX(${(current + 1) / frames.length})`;
    status.textContent = hide ? frames[current].getAttribute('aria-label') : '';
    // Stacked reading mode keeps the address unchanged; the browser would scroll to the fragment.
    if (hide) try { history.replaceState(null, '', `#slide-${current + 1}`); } catch {}
    // In the app the workspace keeps the slide in view, so its edit mode opens at the same slide.
    if (framed) window.parent.postMessage({type: 'distill-slide', slide: current + 1}, '*');
    fit();
  }
  // The click wins (motion rules, after Emil Kowalski): a step first finishes the slide's running entrances, so
  // a quick click never shows step 2 before step 1, and input within 400 ms of the last lands with no motion.
  const SKIM = 400;
  let lastStep = -Infinity;
  function settle(frame, entrancesOnly = false) {
    for (const animation of frame.getAnimations?.({subtree: true}) || []) {
      if (entrancesOnly && animation instanceof CSSTransition) continue;  // figure states retarget instead
      try { animation.finish(); } catch {}
    }
  }
  function move(forward) {
    const now = performance.now(), skimming = now - lastStep < SKIM;
    lastStep = now;
    settle(frames[current], true);
    const arrival = skimming ? 'instant' : undefined;
    if (forward && presenting() && shown < builds[current].length) {
      const item = builds[current][shown++];
      item.classList.remove('build-pending');
      item.classList.add('build-shown');
    } else if (forward && current < frames.length - 1) show(current + 1, false, arrival);
    else if (!forward && presenting() && shown > 0) {
      const item = builds[current][--shown];
      item.classList.remove('build-shown');
      item.classList.add('build-pending');
    } else if (!forward && current > 0) show(current - 1, true, arrival);
    if (skimming) settle(frames[current]);
  }
  const advance = () => move(true), back = () => move(false);
  function setNotes(visible) {
    if (phone) return;
    document.body.classList.toggle('show-notes', visible);
    notesToggle.setAttribute('aria-pressed', String(visible));
    saved.set('distill-lecture-notes', visible ? '1' : '0');
    fit();
  }
  // In the app the deck sits in a sandboxed frame that cannot take full screen itself; the workspace does it.
  const framed = window.parent !== window;
  function fullscreen() {
    if (framed) return window.parent.postMessage({type: 'distill-fullscreen'}, '*');
    if (!document.fullscreenEnabled) return;
    if (document.fullscreenElement) document.exitFullscreen(); else root.requestFullscreen().catch(() => {});
  }

  document.getElementById('prev').addEventListener('click', back);
  document.getElementById('next').addEventListener('click', advance);
  notesToggle.addEventListener('click', () => setNotes(!document.body.classList.contains('show-notes')));
  document.getElementById('print-button').addEventListener('click', () => window.print());
  const full = document.getElementById('fullscreen-button');
  full.hidden = !(document.fullscreenEnabled || framed);
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
  document.addEventListener('keydown', event => {
    if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || outline.open) return;
    // A figure's scrubber and other fields keep their own arrow keys.
    if (event.target.closest?.('input, textarea, select')) return;
    const key = event.key.length === 1 ? event.key.toLowerCase() : event.key;
    if (key === 'n') return setNotes(!document.body.classList.contains('show-notes'));
    if (!presenting()) return;
    const control = event.target.closest?.('button, a, input, textarea, select');
    const step = {ArrowRight: 1, ArrowDown: 1, PageDown: 1, ArrowLeft: -1, ArrowUp: -1, PageUp: -1}[key] ?? (key === ' ' && !control ? (event.shiftKey ? -1 : 1) : 0);
    // A held key never runs through the deck, and a key while the screen is blank only brings the slide back.
    if (step && (event.repeat || blank(false))) return event.preventDefault();
    // Shift with an arrow or Page key skips the remaining build steps, as in Marp.
    if (step && event.shiftKey && key !== ' ') { if (frames[current + step]) show(current + step, step < 0); }
    else if (step) (step > 0 ? advance : back)();
    else if (key === 'Home') show(0);
    else if (key === 'End') show(frames.length - 1, true);
    else if (key === 'f') fullscreen();
    // B or "." blanks the screen, the pause button on most presenter remotes; either brings it back.
    else if (key === 'b' || key === '.') blank(!document.body.classList.contains('blanked'));
    else return;
    event.preventDefault();
  });
  function blank(on) {
    const was = document.body.classList.contains('blanked');
    document.body.classList.toggle('blanked', on);
    status.textContent = on ? (root.lang === 'vi' ? 'Màn hình đang tắt' : 'Screen blanked') : '';
    return was && !on;
  }
  let touchStart = null, pressAt = null;
  deck.addEventListener('pointerdown', event => {
    pressAt = [event.clientX, event.clientY];
    if (event.pointerType !== 'mouse') touchStart = event.clientX;
  });
  deck.addEventListener('pointerup', event => {
    if (touchStart === null || !presenting()) return;
    const distance = event.clientX - touchStart;
    touchStart = null;
    if (Math.abs(distance) > 40) (distance < 0 ? advance : back)();
  });
  // A click on the slide advances, like a presenter remote. Controls, links, figures, notes, drags and
  // selected text keep their clicks.
  deck.addEventListener('click', event => {
    if (!presenting() || event.button !== 0 || event.defaultPrevented) return;
    if (event.target.closest('a, button, input, select, textarea, summary, label, [tabindex], .figure, .notes')) return;
    if (pressAt && Math.hypot(event.clientX - pressAt[0], event.clientY - pressAt[1]) > 6) return;
    if (String(getSelection?.() || '')) return;
    // On a phone a tap on the left edge goes back, as in a photo viewer.
    if (!blank(false)) (phone && event.clientX < innerWidth * .3 ? back : advance)();
  });
  const controls = document.getElementById('controls-toggle');
  controls?.addEventListener('click', () => {
    const on = document.body.classList.toggle('show-controls');
    controls.setAttribute('aria-expanded', String(on));
    controls.setAttribute('aria-label', root.lang === 'vi' ? (on ? 'Ẩn điều khiển' : 'Hiện điều khiển') : (on ? 'Hide controls' : 'Show controls'));
  });
  // One wheel notch or trackpad gesture is one step. After a step the wheel must rest before the next
  // (Marp waits 250 ms too), so trackpad inertia never skips ahead; a scrollable area under the pointer,
  // such as long notes, scrolls instead.
  const WHEEL_STEP = 50, WHEEL_REST = 250;
  let wheelTravel = 0, wheelLocked = false, wheelTimer = 0;
  function scrolls(node, delta) {
    for (; node && node !== deck; node = node.parentElement) {
      if (!/(auto|scroll)/.test(getComputedStyle(node).overflowY) || node.scrollHeight <= node.clientHeight + 1) continue;
      if (delta > 0 ? node.scrollTop + node.clientHeight < node.scrollHeight - 1 : node.scrollTop > 0) return true;
    }
    return false;
  }
  deck.addEventListener('wheel', event => {
    if (!presenting() || event.ctrlKey || outline.open) return;
    const delta = (Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY) * (event.deltaMode ? 40 : 1);
    if (!delta || scrolls(event.target, delta)) return;
    event.preventDefault();
    clearTimeout(wheelTimer);
    wheelTimer = setTimeout(() => { wheelLocked = false; wheelTravel = 0; }, WHEEL_REST);
    if (wheelLocked) return;
    wheelTravel += delta;
    if (Math.abs(wheelTravel) < WHEEL_STEP) return;
    wheelLocked = true;
    if (!blank(false)) (wheelTravel > 0 ? advance : back)();
  }, {passive: false});
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
