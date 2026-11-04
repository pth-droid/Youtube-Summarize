/* Edit mode, in the app only. The renderer marks each text a person may change with data-field; this script makes
   those texts editable in place and reports every change to the workspace, which saves them. It also draws the slide
   rail and the slide tools: a structure edit (hide, move, delete, ...) is a message to the workspace, which makes the
   edit and loads this page again at the slide it names (#at-P.S, counted from 0). The deck sits in a sandbox, so it
   never reaches the server itself. */
(() => {
  'use strict';
  const root = document.documentElement;
  const fields = [...document.querySelectorAll('[data-field]')];
  const frames = [...document.querySelectorAll('.slide-frame')];
  const deck = document.getElementById('deck');
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

  function collect() {
    const changes = new Map(), problems = [];
    for (const node of fields) {
      const text = read(node), changed = text !== node.dataset.original, limit = Number(node.dataset.limit) || 0;
      node.classList.toggle('edited', changed);
      const problem = !text && !lines(node) ? 'empty' : limit && text.length > limit ? 'long' : '';
      node.setAttribute('aria-invalid', String(Boolean(problem)));
      if (problem) problems.push({slide: frames.indexOf(node.closest('.slide-frame')) + 1, problem, length: text.length, limit});
      if (changed) changes.set(place(node), {field: node.dataset.field, span: node.dataset.span || '', text});
    }
    return {changes: [...changes.values()], problems};
  }
  // The editor counts every slide, hidden ones too; the deck leaves them out. The workspace keeps the deck's number, so
  // the same slide is in view when editing ends, and in edit mode opens where the deck was.
  const shownNumber = index => index + 1 - frames.slice(0, index).filter(frame => frame.dataset.hidden).length;
  const shownIndex = number => {
    let seen = 0;
    const found = frames.findIndex(frame => !frame.dataset.hidden && ++seen === number);
    return found < 0 ? frames.length - 1 : found;
  };
  function report() {
    window.parent.postMessage({type: 'distill-edit', version, ...collect(), slide: shownNumber(current() - 1)}, '*');
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

  // ---------- Structure: the slide rail, the slide tools, drag and drop ----------
  const tell = op => window.parent.postMessage({type: 'distill-structure', op}, '*');
  const history = (document.querySelector('meta[name="distill-history"]')?.content || '0,0').split(',').map(Number);
  const at = frame => frame.dataset.slide || frame.dataset.divider || '';
  const spot = value => value.split('.').map(Number);
  const kind = frame => frame.dataset.slide ? 'slide' : frame.dataset.divider ? 'divider' : 'frame';
  const sizes = {};  // slides in each part
  for (const frame of frames) if (frame.dataset.slide) { const [part] = spot(frame.dataset.slide); sizes[part] = (sizes[part] || 0) + 1; }
  const parts = Object.keys(sizes).length;
  const element = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  };
  const jump = number => { if (location.hash !== `#slide-${number}`) location.hash = `#slide-${number}`; };

  // The workspace loads this page at #at-P.S after an edit. The deck's own script has replaced the hash by now, so the
  // address the page was opened at is read from the navigation entry.
  const address = performance.getEntriesByType?.('navigation')[0]?.name || location.href;
  const opened = address.match(/#at-(\d+(?:\.\d+)?)$/), numbered = address.match(/#slide-(\d+)$/);
  if (opened) {
    const start = frames.findIndex(frame => at(frame) === opened[1]);
    if (start >= 0) jump(start + 1);
  } else if (numbered && frames.some(frame => frame.dataset.hidden)) jump(shownIndex(Number(numbered[1])) + 1);

  const tools = element('div', 'edit-tools');
  tools.setAttribute('role', 'toolbar');
  tools.setAttribute('aria-label', 'Slide tools');
  const label = element('span', 'tools-name');
  tools.append(label);
  const buttons = {};
  const tool = (name, text, title, run) => {
    const button = element('button', `tool tool-${name}`, text);
    button.type = 'button';
    button.title = title;
    button.dataset.tool = name;
    button.addEventListener('click', run);
    buttons[name] = button;
    tools.append(button);
  };
  const selected = () => frames[current() - 1];
  const here = () => spot(at(selected()));
  tool('up', 'Move up', 'Move this slide earlier in the deck', () => {
    const [part, index] = here();
    tell({type: 'move', slide: [part, index], to: index > 0 ? [part, index - 1] : [part - 1, sizes[part - 1]]});
  });
  tool('down', 'Move down', 'Move this slide later in the deck', () => {
    const [part, index] = here();
    tell({type: 'move', slide: [part, index], to: index < sizes[part] - 1 ? [part, index + 1] : [part + 1, 0]});
  });
  tool('hide', 'Hide', 'Leave this slide out when presenting and exporting', () => tell({type: selected().dataset.hidden ? 'show' : 'hide', slide: here()}));
  tool('duplicate', 'Duplicate', 'Copy this slide just after itself', () => tell({type: 'duplicate', slide: here()}));
  tool('layout', 'Layout…', 'Show this slide in another layout, with a preview', () => window.parent.postMessage({type: 'distill-layout', slide: here()}, '*'));
  tool('delete', 'Delete', 'Delete this slide; Undo brings it back', () => tell({type: 'delete', slide: here()}));
  tool('add', 'Add slide', 'Add a blank slide after this one', () => {
    const frame = selected(), [part, index] = spot(at(frame));
    tell({type: 'add', part, index: kind(frame) === 'divider' ? 0 : index + 1});
  });
  tools.append(element('span', 'tools-gap'));
  tool('undo', `Undo${history[0] ? ` (${history[0]})` : ''}`, 'Undo the last saved edit', () => tell({type: 'undo'}));
  tool('redo', `Redo${history[1] ? ` (${history[1]})` : ''}`, 'Redo the edit you undid', () => tell({type: 'redo'}));
  buttons.undo.disabled = !history[0];
  buttons.redo.disabled = !history[1];

  const rail = element('nav', 'edit-rail');
  rail.setAttribute('aria-label', 'Slides');
  const list = element('ol', 'rail-list');
  rail.append(list);
  const items = frames.map((frame, index) => {
    const item = element('li', `rail-item rail-${kind(frame)}`);
    item.dataset.at = at(frame);
    if (frame.dataset.hidden) item.classList.add('is-hidden');
    const open = element('button', 'rail-open');
    open.type = 'button';
    open.setAttribute('aria-label', `Slide ${index + 1}: ${frame.getAttribute('aria-label').replace(/^[^:]*: /, '')}${frame.dataset.hidden ? ' (hidden)' : ''}`);
    open.addEventListener('click', () => jump(index + 1));
    open.append(element('span', 'rail-number', String(index + 1).padStart(2, '0')), element('span', 'rail-shot'),
                element('span', 'rail-title', frame.querySelector('h1, h2')?.textContent || ''));
    if (frame.dataset.hidden) open.append(element('span', 'rail-tag', 'Hidden'));
    item.append(open);
    if (kind(frame) === 'slide') item.draggable = true;
    list.append(item);
    return item;
  });
  // A thumbnail is a copy of the slide, scaled down and inert, with the editing marks taken off it.
  function draw(index) {
    const copy = frames[index].querySelector('.slide-box').cloneNode(true);
    for (const node of copy.querySelectorAll('[data-field], [id], [contenteditable]')) {
      for (const name of ['data-field', 'data-span', 'data-limit', 'data-original', 'id', 'contenteditable', 'role', 'spellcheck', 'aria-invalid', 'aria-multiline']) node.removeAttribute(name);
    }
    copy.inert = true;
    copy.setAttribute('aria-hidden', 'true');
    items[index].querySelector('.rail-shot').replaceChildren(copy);
  }
  frames.forEach((_, index) => draw(index));
  let redraw = 0;
  document.addEventListener('input', event => {
    const index = frames.indexOf(event.target.closest?.('.slide-frame'));
    if (index < 0) return;
    clearTimeout(redraw);
    redraw = setTimeout(() => draw(index), 300);
  });

  const shell = element('div', 'edit-shell');
  deck.before(shell);
  shell.append(rail, deck);
  document.querySelector('.deck-bar').after(tools);
  function sync() {
    const position = current() - 1, frame = selected(), type = kind(frame);
    const [part, index] = type === 'slide' ? spot(at(frame)) : [Number(at(frame)), 0];
    items.forEach((item, number) => {
      const open = item.querySelector('.rail-open'), on = number === position;
      item.classList.toggle('is-current', on);
      if (on) { open.setAttribute('aria-current', 'true'); item.scrollIntoView({block: 'nearest'}); } else open.removeAttribute('aria-current');
    });
    label.textContent = type === 'slide' ? `Slide ${position + 1} · part ${part + 1}` : type === 'divider' ? `Part ${part + 1} divider` : `Slide ${position + 1} · made from the deck`;
    for (const name of ['up', 'down', 'hide', 'duplicate', 'layout', 'delete']) buttons[name].disabled = type !== 'slide';
    buttons.add.disabled = type === 'frame';
    if (type === 'slide') {
      buttons.up.disabled = part === 0 && index === 0;
      buttons.down.disabled = part === parts - 1 && index === sizes[part] - 1;
      buttons.hide.textContent = frame.dataset.hidden ? 'Show' : 'Hide';
      buttons.hide.title = frame.dataset.hidden ? 'Put this slide back into the deck' : 'Leave this slide out when presenting and exporting';
    }
  }
  // The slide in view changed: the tools follow it, and the workspace is told which slide to reopen at.
  let moved = 0;
  new MutationObserver(() => { sync(); clearTimeout(moved); moved = setTimeout(report, 30); }).observe(deck, {subtree: true, attributes: true, attributeFilter: ['class']});
  sync();
  // The deck was moved beside the rail, so it fits itself to the room it has now.
  dispatchEvent(new Event('resize'));

  // Drag a content slide in the rail: onto the upper or lower half of another slide, or onto a part's divider to make it
  // that part's first slide. Parts keep one to six slides; the server refuses a move that would break that.
  let dragging = null;
  const clearMarks = () => rail.querySelectorAll('.drop-before, .drop-after, .dragging').forEach(node => node.classList.remove('drop-before', 'drop-after', 'dragging'));
  function target(event) {
    const item = event.target.closest?.('.rail-item');
    if (!dragging || !item) return null;
    const [from, start] = dragging;
    if (item.classList.contains('rail-slide')) {
      const [part, index] = spot(item.dataset.at), box = item.getBoundingClientRect(), after = event.clientY > box.top + box.height / 2;
      let to = index + (after ? 1 : 0);
      if (part === from && start < to) to -= 1;
      return {to: [part, to], item, side: after ? 'drop-after' : 'drop-before', same: part === from && to === start};
    }
    if (item.classList.contains('rail-divider')) return {to: [Number(item.dataset.at), 0], item, side: 'drop-after', same: false};
    return null;
  }
  list.addEventListener('dragstart', event => {
    const item = event.target.closest?.('.rail-slide');
    if (!item) return;
    dragging = spot(item.dataset.at);
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', item.dataset.at);
    item.classList.add('dragging');
  });
  list.addEventListener('dragover', event => {
    const found = target(event);
    clearMarks();
    if (!found || found.same) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
    found.item.classList.add(found.side);
    items.find(item => item.dataset.at === dragging.join('.'))?.classList.add('dragging');
  });
  list.addEventListener('drop', event => {
    const found = target(event), from = dragging;
    clearMarks();
    dragging = null;
    if (!found || found.same || !from) return;
    event.preventDefault();
    tell({type: 'move', slide: from, to: found.to});
  });
  list.addEventListener('dragend', () => { clearMarks(); dragging = null; });
  report();
})();
