/* Edit mode, in the app only. The renderer marks each text a person may change with data-field; this script makes
   those texts editable in place and reports every change to the workspace, which saves them. */
(() => {
  'use strict';
  const root = document.documentElement;
  const fields = [...document.querySelectorAll('[data-field]')];
  const frames = [...document.querySelectorAll('.slide-frame')];
  const version = document.querySelector('meta[name="distill-version"]')?.content || '';
  const lines = node => node.hasAttribute('data-lines');
  // Text as saved: notes keep their paragraphs, every other text is one line. Read from the markup, not innerText,
  // which is empty on slides that are not in view.
  function read(node) {
    if (!lines(node)) return node.textContent.replace(/\s+/g, ' ').trim();
    let text = '';
    const walk = parent => {
      for (const child of parent.childNodes) {
        if (child.nodeType === Node.TEXT_NODE) text += child.data;
        else if (child.nodeName === 'BR') text += '\n';
        else { text += '\n'; walk(child); text += '\n'; }
      }
    };
    walk(node);
    return text.split('\n').map(line => line.replace(/\s+/g, ' ').trim()).filter(Boolean).join('\n');
  }
  // One text can show in several places, such as a part title on the agenda and on its section slide.
  const place = node => `${node.dataset.field}|${node.dataset.span || ''}`;
  const current = () => Math.max(0, frames.findIndex(frame => frame.classList.contains('is-current'))) + 1;

  root.classList.add('editing');
  for (const node of fields) {
    try { node.contentEditable = 'plaintext-only'; } catch { node.contentEditable = 'true'; }
    node.spellcheck = true;
    node.setAttribute('role', 'textbox');
    if (lines(node)) node.setAttribute('aria-multiline', 'true');
    node.dataset.original = read(node);
  }

  function report() {
    const changes = new Map(), problems = [];
    for (const node of fields) {
      const text = read(node), changed = text !== node.dataset.original, limit = Number(node.dataset.limit) || 0;
      node.classList.toggle('edited', changed);
      const problem = !text && !lines(node) ? 'empty' : limit && text.length > limit ? 'long' : '';
      node.setAttribute('aria-invalid', String(Boolean(problem)));
      if (problem) problems.push({slide: frames.indexOf(node.closest('.slide-frame')) + 1, problem, length: text.length, limit});
      if (changed) changes.set(place(node), {field: node.dataset.field, span: node.dataset.span || '', text});
    }
    window.parent.postMessage({type: 'distill-edit', version, changes: [...changes.values()], problems, slide: current()}, '*');
  }

  document.addEventListener('input', event => {
    const node = event.target.closest?.('[data-field]');
    if (!node) return;
    for (const twin of fields) if (twin !== node && place(twin) === place(node)) twin.textContent = read(node);
    report();
  });
  // Typing stays in the text: the deck's keys (arrows, space, N, F, B) wait outside it. Enter ends a one-line text;
  // Esc puts the text back as it was.
  addEventListener('keydown', event => {
    const node = event.target.closest?.('[data-field]');
    if (!node) return;
    event.stopPropagation();
    if (event.key === 'Escape') {
      event.preventDefault();
      for (const twin of fields) if (place(twin) === place(node)) twin.textContent = twin.dataset.original;
      report();
      node.blur();
    } else if (event.key === 'Enter' && !lines(node)) {
      event.preventDefault();
      node.blur();
    }
  }, true);
  // A click on a slide places the caret instead of advancing. Links, controls and figures keep their clicks.
  addEventListener('click', event => {
    if (event.target.closest?.('.slide-frame') && !event.target.closest('a, button, input, select, label, summary, .figure')) event.preventDefault();
  }, true);
  // Notes are text to edit too, so they show.
  if (!document.body.classList.contains('show-notes')) document.getElementById('notes-toggle')?.click();
  report();
})();
