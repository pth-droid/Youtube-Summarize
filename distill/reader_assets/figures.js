/* Process figures. The server HTML already holds every label, value and table;
   this script draws the charts at the real width and adds the scrubber, layers and levers. */
(() => {
  'use strict';
  const vi = document.documentElement.lang === 'vi', t = (en, vn) => vi ? vn : en;
  const NS = 'http://www.w3.org/2000/svg';
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  function svg(tag, attrs = {}, parent, text) {
    const node = document.createElementNS(NS, tag);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    if (text !== undefined) node.textContent = text;
    parent?.append(node);
    return node;
  }
  function html(tag, cls, text) { const node = document.createElement(tag); if (cls) node.className = cls; if (text !== undefined) node.textContent = text; return node; }
  const clock = seconds => { const value = Math.round(seconds), size = Math.abs(value); return `${value < 0 ? '-' : ''}${Math.floor(size / 60)}:${String(size % 60).padStart(2, '0')}`; };
  const fmt = value => (Math.abs(value) >= 100 || Number.isInteger(value) ? Math.round(value) : +value.toFixed(2))
    .toLocaleString(vi ? 'vi-VN' : 'en-US', {useGrouping: false, maximumFractionDigits: 2});
  const textWidth = (text, size = 12) => text.length * size * .56;
  // Scale shown by a transformed slide; overlay coordinates are drawn unscaled.
  const scaleOf = element => (element.getBoundingClientRect().width / element.offsetWidth) || 1;
  function nice(min, max, count = 4) {
    if (min === max) { min -= 1; max += 1; }
    const raw = (max - min) / count, power = 10 ** Math.floor(Math.log10(raw));
    const step = [1, 2, 2.5, 5, 10].map(multiple => multiple * power).find(value => value >= raw);
    const low = Math.floor(min / step) * step, high = Math.ceil(max / step) * step, ticks = [];
    for (let value = low; value <= high + step / 2; value += step) ticks.push(+value.toFixed(10));
    return {low, high, ticks};
  }
  function timeTicks(low, high, width) {
    const most = Math.max(2, Math.floor(width / 80));
    const step = [5, 10, 15, 30, 60, 120, 180, 300, 600, 900, 1200, 1800, 3600].find(value => (high - low) / value <= most) || 3600;
    const ticks = [];
    for (let value = Math.ceil(low / step) * step; value <= high + 1e-9; value += step) ticks.push(value);
    return ticks;
  }
  // Monotone cubic curve: an illustrative shape never overshoots the points it was given.
  function smooth(points) {
    const n = points.length;
    if (n < 3) return 'M ' + points.map(p => p.join(' ')).join(' L ');
    const dx = [], slope = [];
    for (let i = 0; i < n - 1; i++) { dx[i] = points[i + 1][0] - points[i][0]; slope[i] = (points[i + 1][1] - points[i][1]) / dx[i]; }
    const tangent = [slope[0]];
    for (let i = 1; i < n - 1; i++) tangent[i] = slope[i - 1] * slope[i] <= 0 ? 0 : 3 * (dx[i - 1] + dx[i]) / ((2 * dx[i] + dx[i - 1]) / slope[i - 1] + (dx[i] + 2 * dx[i - 1]) / slope[i]);
    tangent[n - 1] = slope[n - 2];
    let d = `M ${points[0][0]} ${points[0][1]}`;
    for (let i = 0; i < n - 1; i++) {
      const h = dx[i] / 3;
      d += ` C ${points[i][0] + h} ${points[i][1] + tangent[i] * h} ${points[i + 1][0] - h} ${points[i + 1][1] - tangent[i + 1] * h} ${points[i + 1][0]} ${points[i + 1][1]}`;
    }
    return d;
  }
  // Redraw only when the box really changes size; drawing itself can resize a box once.
  function observe(element, callback) {
    let last = '';
    new ResizeObserver(() => {
      const size = `${element.clientWidth}x${element.closest('.slide') ? element.clientHeight : ''}`;
      if (size === last) return;
      last = size;
      callback();
    }).observe(element);
  }
  const normalUnit = unit => (unit || '').trim().replace('℃', '°C').replace('℉', '°F').replace(/^C$/i, '°C').replace(/^F$/i, '°F');

  /* Roast logs are read here, in the browser. Nothing is uploaded or saved. */
  function pythonLiteral(source) {
    let i = 0;
    const space = () => { while (i < source.length && /\s/.test(source[i])) i++; };
    function sequence(close, add) {
      space();
      if (source[i] === close) { i++; return; }
      for (;;) {
        add();
        space();
        const next = source[i++];
        if (next === ',') { space(); if (source[i] === close) { i++; return; } continue; }
        if (next === close) return;
        throw new Error('Unexpected character');
      }
    }
    function value() {
      space();
      const c = source[i];
      if (c === '{') { i++; const out = {}; sequence('}', () => { const key = value(); space(); if (source[i++] !== ':') throw new Error('Missing colon'); out[key] = value(); }); return out; }
      if (c === '[' || c === '(') { i++; const out = []; sequence(c === '[' ? ']' : ')', () => out.push(value())); return out; }
      if (c === "'" || c === '"' || (/[ubr]/i.test(c) && /['"]/.test(source[i + 1]))) {
        if (c !== "'" && c !== '"') i++;
        const quote = source[i++];
        let text = '';
        while (i < source.length && source[i] !== quote) {
          if (source[i] === '\\') {
            const next = source[i + 1];
            if (next === 'u') { text += String.fromCharCode(parseInt(source.slice(i + 2, i + 6), 16)); i += 6; continue; }
            text += {n: '\n', t: '\t', r: '\r'}[next] ?? next; i += 2;
          } else text += source[i++];
        }
        i++;
        return text;
      }
      const match = /^(?:-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?|True|False|None|nan|-?inf)/.exec(source.slice(i, i + 40));
      if (!match) throw new Error('Unknown value');
      i += match[0].length;
      return {True: true, False: false, None: null, nan: NaN, inf: Infinity, '-inf': -Infinity}[match[0]] ?? Number(match[0]);
    }
    return value();
  }
  const mine = name => vi ? `${name} của bạn` : `Your ${name}`;
  const eventNames = () => [t('Dry end', 'Kết thúc sấy'), t('First crack', 'Nứt lần 1'), t('First crack end', 'Hết nứt lần 1'),
    t('Second crack', 'Nứt lần 2'), t('Second crack end', 'Hết nứt lần 2'), t('Drop', 'Ra lò')];
  function fromArtisan(profile) {
    const times = profile.timex, bean = profile.temp2, air = profile.temp1;
    if (!Array.isArray(times) || !Array.isArray(bean)) throw new Error('Not an Artisan profile');
    const index = profile.timeindex || [], charge = index[0] >= 0 ? index[0] : 0, zero = times[charge] || 0;
    const drop = index[6] > 0 ? times[index[6]] - zero : Infinity;
    const unit = String(profile.mode || 'C').toUpperCase() === 'F' ? '°F' : '°C';
    // Artisan stores -1 for a missing reading.
    const points = values => times.map((time, k) => ({x: time - zero, y: values[k]})).filter(p => p.x >= 0 && p.x <= drop && Number.isFinite(p.y) && p.y > -1);
    const series = [{label: mine('BT'), unit, points: points(bean), slot: 4}];
    if (Array.isArray(air)) series.push({label: mine('ET'), unit, points: points(air), slot: 5});
    const names = eventNames(), events = [];
    index.slice(1, 7).forEach((k, n) => { if (k > 0 && times[k] !== undefined) events.push({at: times[k] - zero, label: names[n]}); });
    return finish(series, events);
  }
  function seconds(value) {
    value = (value || '').trim();
    if (!value) return NaN;
    if (value.includes(':')) return value.split(':').map(Number).reduce((total, part) => total * 60 + part, 0);
    return Number(value.replace(',', '.'));
  }
  function fromTable(text) {
    const lines = text.split(/\r?\n/).filter(line => line.trim());
    const delimiter = lines.slice(0, 3).some(line => line.includes('\t')) ? '\t' : lines[0].includes(';') && !lines[0].includes(',') ? ';' : ',';
    let rows = lines.map(line => line.split(delimiter).map(cell => cell.trim().replace(/^"|"$/g, '')));
    const meta = {};
    // Artisan's CSV export puts a row of "Key:value" cells before the column names.
    if (rows[0].some(cell => /^(Date|Unit|CHARGE|DROP):/.test(cell))) {
      rows[0].forEach(cell => { const at = cell.indexOf(':'); if (at > 0) meta[cell.slice(0, at)] = cell.slice(at + 1); });
      rows = rows.slice(1);
    }
    const head = rows[0], body = rows.slice(1);
    let time = head.findIndex(name => /^time2$/i.test(name));
    if (time < 0) time = head.findIndex(name => /time|thời gian|giây|sec/i.test(name));
    if (time < 0) time = 0;
    const metaUnit = /F/i.test(meta.Unit || '') ? '°F' : '°C', series = [];
    head.forEach((name, column) => {
      if (column === time || /^time1$|event|sự kiện/i.test(name)) return;
      const points = body.map(row => ({x: seconds(row[time]), y: Number((row[column] || '').replace(',', '.'))}))
        .filter(p => Number.isFinite(p.x) && Number.isFinite(p.y) && p.y > -1).sort((a, b) => a.x - b.x);
      const declared = /\(([^)]+)\)|\[([^\]]+)\]/.exec(name), label = name.replace(/\s*[([].*$/, '');
      const unit = declared ? (declared[1] || declared[2]) : /^(BT|ET)$/i.test(label) ? metaUnit : '';
      series.push({label: mine(label), unit, points, slot: series.length % 2 ? 5 : 4});
    });
    const keys = ['DRYe', 'FCs', 'FCe', 'SCs', 'SCe', 'DROP'], names = eventNames();
    const events = keys.map((key, n) => ({at: seconds(meta[key]), label: names[n]})).filter(event => Number.isFinite(event.at) && event.at > 0);
    return finish(series, events);
  }
  function finish(series, events) {
    series = series.filter(s => s.points.length >= 2).slice(0, 3);
    if (!series.length) throw new Error('No readable series');
    for (const s of series) if (s.points.length > 400) { const step = s.points.length / 400; s.points = Array.from({length: 400}, (_, k) => s.points[Math.floor(k * step)]); }
    // Rate of rise: bean temperature change per minute over the previous 30 seconds, as roasting software shows it.
    const bean = series.find(s => /BT/i.test(s.label) && /°[CF]$/.test(normalUnit(s.unit)));
    if (bean && !series.some(s => /\/min/.test(s.unit))) {
      const p = bean.points, rise = [];
      for (let k = 0, j = 0; k < p.length; k++) {
        while (j < k && p[k].x - p[j + 1].x >= 30) j++;
        if (p[k].x >= 60 && p[k].x - p[j].x >= 20) rise.push({x: p[k].x, y: (p[k].y - p[j].y) / (p[k].x - p[j].x) * 60});
      }
      if (rise.length >= 2) series.push({label: t('Your RoR (computed from BT)', 'RoR của bạn (tính từ BT)'), unit: `${normalUnit(bean.unit)}/min`, points: rise, slot: 4});
    }
    const xs = series.flatMap(s => [s.points[0].x, s.points[s.points.length - 1].x]);
    return {series, events, start: Math.min(...xs), end: Math.max(...xs)};
  }
  function readLog(text) {
    const trimmed = text.replace(/^\uFEFF/, '').trim();
    return trimmed.startsWith('{') ? fromArtisan(pythonLiteral(trimmed)) : fromTable(trimmed);
  }

  /* Process: phases, quantity panels, compound lanes, one scrubber for all of them. */
  function process(root, spec) {
    const chart = root.querySelector('.fig-chart'), scrub = root.querySelector('.fig-scrubber');
    const readout = root.querySelector('.fig-readout'), announce = root.querySelector('.fig-announce');
    const play = root.querySelector('.fig-play'), chips = [...root.querySelectorAll('.fig-phases [data-phase]')];
    // State cards and compound cells may sit on the next slide; they share this figure's key.
    const cards = () => [...document.querySelectorAll(`[data-key="${root.dataset.key}"] [data-phase]:not(button)`)];
    const phases = spec.phases, timed = spec.axis === 'time', ordinal = !timed && !spec.axis_unit;
    const at = value => timed ? clock(value) : `${fmt(value)} ${spec.axis_unit || ''}`.trim();
    let log = null, current = Number(scrub.value), running = null, lastPhase = -1;
    let x = () => 0, cursor = null, handle = null, bands = [], low = phases[0].start, high = phases[phases.length - 1].end;

    function panels() {
      const list = [];
      const find = (unit, illustrative) => list.find(p => p.unit === unit && p.illustrative === illustrative);
      for (const s of spec.series) {
        const unit = normalUnit(s.unit), illustrative = s.provenance === 'illustrative';
        let panel = find(unit, illustrative);
        if (!panel) list.push(panel = {unit, illustrative, series: []});
        panel.series.push({...s, unit, slot: panel.series.length + 1});
      }
      for (const s of log?.series || []) {
        const unit = normalUnit(s.unit);
        let panel = find(unit, false);
        if (!panel) { if (list.length >= 4) continue; list.push(panel = {unit, illustrative: false, series: []}); }
        panel.series.push({...s, unit, measured: true});
      }
      return list;
    }
    function draw() {
      const width = chart.clientWidth;
      if (!width) return;
      const slide = !!root.closest('.slide'), narrow = width < 560;
      chart.replaceChildren();
      const available = chart.clientHeight;
      const groups = panels(), lanes = spec.compounds, events = [...spec.events, ...(log?.events || []).map(e => ({...e, log: true}))];
      low = Math.min(phases[0].start, log ? log.start : Infinity);
      high = Math.max(phases[phases.length - 1].end, log ? log.end : -Infinity);
      scrub.min = low; scrub.max = high; scrub.step = (high - low) / 400;
      // Slides draw on the 1280-wide canvas, so their text is set larger.
      const size = slide ? 15 : 12, left = slide ? 62 : 50, right = narrow ? 12 : slide ? 132 : 104;
      const eventRow = events.length ? size * 2 + 10 : 0, band = slide ? 36 : 30, axis = slide ? 30 : 24, gap = slide ? 40 : 34;
      const laneHeight = 24, laneLabel = 18, laneStep = laneHeight + laneLabel + 6, lanesHeight = lanes.length ? 10 + lanes.length * laneStep : 0;
      let panelHeight = Math.max(110, Math.min(220, width * .26));
      if (slide && available && groups.length && !chart.classList.contains('compact')) panelHeight = Math.max(56, (available - 40 - eventRow - band - axis - lanesHeight) / groups.length - gap);
      const height = eventRow + band + groups.length * (panelHeight + gap) + lanesHeight + axis;
      const plot = svg('svg', {width, height, viewBox: `0 0 ${width} ${height}`, role: 'presentation'}, chart);
      x = value => left + (value - low) / (high - low) * (width - left - right);
      const top = eventRow + band, bottom = height - axis;

      // Event labels, staggered over two rows when they would collide.
      const placed = [];
      events.sort((a, b) => a.at - b.at).forEach(event => {
        const label = event.label.length > 22 ? event.label.slice(0, 21) + '…' : event.label, w = textWidth(label, size);
        const row = placed.some(p => p.row === 0 && Math.abs(p.x - x(event.at)) < (p.w + w) / 2 + 6) ? 1 : 0;
        placed.push({x: x(event.at), w, row});
        const anchor = x(event.at) + w / 2 > width ? 'end' : x(event.at) - w / 2 < 0 ? 'start' : 'middle';
        svg('text', {x: x(event.at), y: size + row * (size + 4), 'text-anchor': anchor, class: event.log ? '' : 'fig-label'}, plot, label);
      });
      // Phase band.
      bands = phases.map((phase, index) => {
        const rect = svg('rect', {x: x(phase.start), y: eventRow, width: Math.max(1, x(phase.end) - x(phase.start)), height: band, class: `fig-band${index % 2 ? ' alt' : ''}`}, plot);
        const room = x(phase.end) - x(phase.start) - 8, label = textWidth(phase.label, size) <= room ? phase.label : textWidth(String(index + 1), size) <= room ? String(index + 1) : '';
        if (label) svg('text', {x: (x(phase.start) + x(phase.end)) / 2, y: eventRow + band / 2 + 4, 'text-anchor': 'middle', class: 'fig-label'}, plot, label);
        return rect;
      });
      // Quantity panels: one unit each, so there is never a second y-axis.
      const labels = [];
      groups.forEach((group, index) => {
        const y0 = top + index * (panelHeight + gap) + gap - 4, y1 = y0 + panelHeight;
        const values = group.series.flatMap(s => s.points.map(p => p.y));
        const scale = nice(Math.min(...values), Math.max(...values), Math.max(2, Math.min(4, Math.floor(panelHeight / (size * 2.4)))));
        const y = value => y1 - (value - scale.low) / (scale.high - scale.low) * (y1 - y0);
        const title = group.illustrative ? t('Illustrative shape · no real values', 'Hình dáng minh họa · không phải số liệu thật') : group.unit || t('Value', 'Giá trị');
        svg('text', {x: left, y: y0 - 10, class: group.illustrative ? '' : 'fig-label'}, plot, title);
        scale.ticks.forEach(tick => {
          svg('line', {x1: left, x2: width - right, y1: y(tick), y2: y(tick), class: tick === scale.low ? 'fig-baseline' : 'fig-grid'}, plot);
          if (!group.illustrative) svg('text', {x: left - 6, y: y(tick) + 4, 'text-anchor': 'end', class: 'fig-tick'}, plot, fmt(tick));
        });
        group.series.forEach(s => {
          const points = s.points.map(p => [x(p.x), y(p.y)]), cls = `s${s.slot}`;
          if (s.provenance === 'illustrative') svg('path', {d: smooth(points), class: `fig-line ${cls}`}, plot);
          else if (s.provenance === 'source') {
            svg('path', {d: 'M ' + points.map(p => p.join(' ')).join(' L '), class: `fig-join ${cls}`}, plot);
            points.forEach(([px, py]) => svg('circle', {cx: px, cy: py, r: 4.5, class: `fig-dot ${cls}`}, plot));
          } else svg('path', {d: 'M ' + points.map(p => p.join(' ')).join(' L '), class: `fig-line ${cls}`}, plot);
          const [ex, ey] = points[points.length - 1];
          if (!narrow && !labels.some(p => Math.abs(p - ey) < size + 1)) {
            labels.push(ey);
            svg('text', {x: ex + 8, y: ey + 4, class: 'fig-label'}, plot, s.label.length > 16 ? s.label.slice(0, 15) + '…' : s.label);
          }
        });
      });
      // Compound lanes: relative amounts per phase, one hue, height carries the amount.
      const lanesTop = top + groups.length * (panelHeight + gap) + 10;
      lanes.forEach((lane, index) => {
        const y0 = lanesTop + index * laneStep, base = y0 + laneLabel + laneHeight;
        svg('text', {x: left, y: y0 + 13, class: 'fig-label'}, plot, lane.name);
        svg('rect', {x: left, y: base - laneHeight, width: Math.max(0, width - left - right), height: laneHeight, class: 'fig-lane-track'}, plot);
        svg('line', {x1: left, x2: width - right, y1: base, y2: base, class: 'fig-baseline'}, plot);
        let d = '', line = '';
        phases.forEach((phase, k) => {
          const h = lane.levels[k] / 4 * laneHeight, a = x(phase.start), b = x(phase.end);
          d += `M ${a} ${base} L ${a} ${base - h} L ${b} ${base - h} L ${b} ${base} Z `;
          line += `M ${a} ${base - h} L ${b} ${base - h} `;
        });
        svg('path', {d, class: 'fig-lane-area'}, plot);
        svg('path', {d: line, class: 'fig-lane-line'}, plot);
      });
      phases.slice(1).forEach(phase => svg('line', {x1: x(phase.start), x2: x(phase.start), y1: top, y2: bottom, class: 'fig-boundary'}, plot));
      events.forEach(event => svg('line', {x1: x(event.at), x2: x(event.at), y1: eventRow - 4, y2: bottom, class: `fig-event${event.log ? ' log' : ''}`}, plot));
      // Axis.
      // Phases in order only: positions carry no value, so the axis shows no numbers.
      const ticks = ordinal ? [] : timed ? timeTicks(low, high, width - left - right) : nice(low, high, Math.max(2, Math.floor(width / 90))).ticks.filter(v => v >= low && v <= high);
      svg('line', {x1: left, x2: width - right, y1: bottom, y2: bottom, class: 'fig-baseline'}, plot);
      ticks.forEach(tick => svg('text', {x: x(tick), y: bottom + 16, 'text-anchor': 'middle', class: 'fig-tick'}, plot, timed ? clock(tick) : fmt(tick)));
      cursor = svg('line', {y1: eventRow, y2: bottom, class: 'fig-cursor'}, plot);
      handle = svg('circle', {cy: eventRow, r: 5, class: 'fig-cursor-handle'}, plot);
      const hit = svg('rect', {x: left, y: eventRow, width: Math.max(0, width - left - right), height: bottom - eventRow, class: 'fig-hit'}, plot);
      hit.addEventListener('pointermove', event => {
        const box = plot.getBoundingClientRect(), position = (event.clientX - box.left) * width / box.width;
        stop();
        set(low + (position - left) / (width - left - right) * (high - low));
      });
      // Legend: always present when there are two or more lines.
      const keyed = groups.flatMap(g => g.series);
      if (keyed.length > 1 || keyed.some(s => s.provenance === 'source')) {
        const legend = html('ul', 'fig-key-row');
        keyed.forEach(s => {
          const item = html('li'), key = html('span', `fig-line-key s${s.slot}${s.provenance === 'source' ? ' dashed' : ''}`);
          item.append(key, document.createTextNode(s.label + (s.unit ? ` (${s.unit})` : '')));
          legend.append(item);
        });
        if (keyed.some(s => s.provenance === 'source')) legend.append(html('li', '', t('Dots: values stated in the source; dashes only join them.', 'Chấm: số liệu nguồn nêu; nét đứt chỉ nối các chấm.')));
        chart.append(legend);
      }
      set(current, false);
    }
    function valueAt(s, value) {
      const p = s.points;
      if (value < p[0].x || value > p[p.length - 1].x || s.provenance === 'illustrative') return null;
      if (s.provenance === 'source') {
        const near = p.find(q => Math.abs(q.x - value) <= (high - low) * .015);
        return near ? `${s.label} ${fmt(near.y)} ${s.unit}`.trim() + t(' (stated)', ' (theo nguồn)') : null;
      }
      for (let k = 0; k < p.length - 1; k++) if (value <= p[k + 1].x) {
        const share = (value - p[k].x) / ((p[k + 1].x - p[k].x) || 1), y = p[k].y + share * (p[k + 1].y - p[k].y);
        return `${s.label} ${s.measured ? '' : '≈ '}${fmt(y)} ${s.unit}`.trim() + (s.measured ? '' : t(' (reference)', ' (tham khảo)'));
      }
      return null;
    }
    function set(value, speak = true) {
      current = Math.max(low, Math.min(high, value));
      scrub.value = current;
      if (cursor) { cursor.setAttribute('x1', x(current)); cursor.setAttribute('x2', x(current)); handle.setAttribute('cx', x(current)); }
      let index = phases.findIndex(phase => current >= phase.start && current <= phase.end);
      if (index < 0) index = current < phases[0].start ? 0 : phases.length - 1;
      const phase = phases[index];
      bands.forEach((band, k) => band.classList.toggle('current', k === index));
      chips.forEach(chip => chip.setAttribute('aria-pressed', String(chip.dataset.phase === phase.id)));
      cards().forEach(card => card.classList.toggle('is-current', card.dataset.phase === phase.id));
      const values = [...spec.series, ...(log?.series || []).map(s => ({...s, measured: true}))].map(s => valueAt({...s, unit: normalUnit(s.unit)}, current)).filter(Boolean);
      readout.replaceChildren(html('b', '', ordinal ? phase.label : `${at(current)} · ${phase.label}`), document.createTextNode(phase.note ? ` — ${phase.note}` : ''));
      if (values.length) { readout.append(document.createElement('br'), document.createTextNode(values.join(' · '))); }
      if (speak && index !== lastPhase) announce.textContent = `${phase.label}. ${phase.note || ''}`;
      lastPhase = index;
    }
    function stop() {
      if (!running) return;
      running();
      running = null;
      play.setAttribute('aria-pressed', 'false');
      play.textContent = t('Play', 'Chạy');
    }
    play.addEventListener('click', () => {
      if (running) return stop();
      if (current >= high - (high - low) * .01) set(low);
      play.setAttribute('aria-pressed', 'true');
      play.textContent = t('Pause', 'Dừng');
      if (reduced.matches) {
        // Without motion, step from phase to phase.
        const timer = setInterval(() => {
          const next = phases.find(phase => (phase.start + phase.end) / 2 > current + 1e-6);
          if (!next) return stop();
          set((next.start + next.end) / 2);
        }, 1600);
        running = () => clearInterval(timer);
        return;
      }
      let last = performance.now(), frame = 0;
      const tick = now => {
        set(current + (now - last) / 14000 * (high - low));
        last = now;
        if (current >= high) return stop();
        frame = requestAnimationFrame(tick);
      };
      frame = requestAnimationFrame(tick);
      running = () => cancelAnimationFrame(frame);
    });
    scrub.addEventListener('input', () => { stop(); set(Number(scrub.value)); });
    chips.forEach(chip => chip.addEventListener('click', () => {
      const phase = phases.find(p => p.id === chip.dataset.phase);
      stop();
      set((phase.start + phase.end) / 2);
    }));
    cards().filter(card => card.classList.contains('fig-state')).forEach(card => card.addEventListener('click', () => chips.find(chip => chip.dataset.phase === card.dataset.phase)?.click()));
    const logButton = root.querySelector('.fig-log'), logFile = root.querySelector('.fig-log-file'), logStatus = root.querySelector('.fig-log-status');
    logButton?.addEventListener('click', () => {
      if (!log) return logFile.click();
      log = null;
      logButton.textContent = logButton.dataset.label;
      logStatus.textContent = '';
      draw();
    });
    logFile?.addEventListener('change', async () => {
      const file = logFile.files[0];
      logFile.value = '';
      if (!file) return;
      try {
        log = readLog(await file.text());
        logButton.textContent = t('Remove the log', 'Bỏ log');
        logStatus.textContent = t(`${file.name}: ${log.series.map(s => s.label).join(', ')}. Read in this browser only; nothing is uploaded or saved.`,
          `${file.name}: ${log.series.map(s => s.label).join(', ')}. Chỉ đọc trong trình duyệt này; không tải lên hay lưu lại.`);
        draw();
      } catch {
        log = null;
        logStatus.textContent = t('This file could not be read. Use an Artisan .alog file, an Artisan CSV export, or a CSV with a time column.',
          'Không đọc được tệp này. Hãy dùng tệp .alog của Artisan, tệp CSV xuất từ Artisan, hoặc CSV có cột thời gian.');
      }
    });
    observe(chart, draw);
    set(current, false);
  }

  /* Region map: two quantities and the named regions between them. */
  function regionMap(root, spec) {
    const chart = root.querySelector('.fig-chart'), items = [...root.querySelectorAll('.fig-regions [data-region]')];
    let active = 0, rects = [];
    function highlight(number) {
      active = active === number ? 0 : number;
      items.forEach(item => item.classList.toggle('active', Number(item.dataset.region) === active));
      rects.forEach((rect, k) => rect.classList.toggle('active', k + 1 === active));
    }
    function draw() {
      const width = chart.clientWidth;
      if (!width) return;
      chart.replaceChildren();
      const slide = !!root.closest('.slide'), available = chart.clientHeight;
      const height = slide && available ? Math.max(220, available) : Math.max(240, Math.min(440, width * .66));
      const size = slide ? 15 : 12, left = slide ? 70 : 58, bottom = slide ? 52 : 44, top = 10, right = 14, numbers = spec.provenance !== 'illustrative';
      const plot = svg('svg', {width, height, viewBox: `0 0 ${width} ${height}`, role: 'presentation'}, chart);
      const x = v => left + (v - spec.x_min) / (spec.x_max - spec.x_min) * (width - left - right);
      const y = v => height - bottom - (v - spec.y_min) / (spec.y_max - spec.y_min) * (height - bottom - top);
      nice(spec.y_min, spec.y_max, 5).ticks.filter(v => v >= spec.y_min && v <= spec.y_max).forEach(tick => {
        svg('line', {x1: left, x2: width - right, y1: y(tick), y2: y(tick), class: 'fig-grid'}, plot);
        if (numbers) svg('text', {x: left - 6, y: y(tick) + 4, 'text-anchor': 'end', class: 'fig-tick'}, plot, fmt(tick));
      });
      nice(spec.x_min, spec.x_max, Math.max(2, Math.floor(width / 110))).ticks.filter(v => v >= spec.x_min && v <= spec.x_max).forEach(tick => {
        svg('line', {x1: x(tick), x2: x(tick), y1: top, y2: height - bottom, class: 'fig-grid'}, plot);
        if (numbers) svg('text', {x: x(tick), y: height - bottom + 16, 'text-anchor': 'middle', class: 'fig-tick'}, plot, fmt(tick));
      });
      rects = spec.regions.map((region, k) => {
        const rect = svg('rect', {x: x(region.x_min), y: y(region.y_max), width: Math.max(2, x(region.x_max) - x(region.x_min)),
          height: Math.max(2, y(region.y_min) - y(region.y_max)), class: `fig-region${region.emphasis ? ' emphasis' : ''}`}, plot);
        svg('title', {}, rect, region.label);
        rect.addEventListener('click', () => highlight(k + 1));
        return rect;
      });
      spec.regions.forEach((region, k) => {
        const w = x(region.x_max) - x(region.x_min), h = y(region.y_min) - y(region.y_max);
        const label = textWidth(`${k + 1} ${region.label}`, size) + 10 <= w && h >= size + 10 ? `${k + 1} ${region.label}` : String(k + 1);
        if (h >= size + 4 && w >= size + 4) svg('text', {x: x(region.x_min) + 6, y: y(region.y_max) + size + 3, class: 'fig-label'}, plot, label);
      });
      spec.points.forEach(point => {
        svg('circle', {cx: x(point.x), cy: y(point.y), r: 5, class: 'fig-point'}, plot);
        const end = x(point.x) + 8 + textWidth(point.label, size) > width - right;
        svg('text', {x: x(point.x) + (end ? -8 : 8), y: y(point.y) - 7, 'text-anchor': end ? 'end' : 'start', class: 'fig-label'}, plot, point.label);
      });
      svg('line', {x1: left, x2: width - right, y1: height - bottom, y2: height - bottom, class: 'fig-baseline'}, plot);
      svg('line', {x1: left, x2: left, y1: top, y2: height - bottom, class: 'fig-baseline'}, plot);
      const name = (label, unit) => `${label}${unit ? ` (${unit})` : ''}${numbers ? '' : ' →'}`;
      svg('text', {x: (left + width - right) / 2, y: height - 8, 'text-anchor': 'middle', class: 'fig-label'}, plot, name(spec.x_label, spec.x_unit));
      svg('text', {x: 14, y: (top + height - bottom) / 2, 'text-anchor': 'middle', class: 'fig-label', transform: `rotate(-90 14 ${(top + height - bottom) / 2})`}, plot, name(spec.y_label, spec.y_unit));
      rects.forEach((rect, k) => rect.classList.toggle('active', k + 1 === active));
    }
    items.forEach(item => item.querySelector('.fig-region-button').addEventListener('click', () => highlight(Number(item.dataset.region))));
    observe(chart, draw);
  }

  /* Apparatus: flow layers, motion and numbered parts. */
  function apparatus(root) {
    root.querySelectorAll('.fig-layer').forEach(button => button.addEventListener('click', () => {
      const on = button.getAttribute('aria-pressed') !== 'true';
      button.setAttribute('aria-pressed', String(on));
      root.querySelectorAll(`.flow[data-kind="${button.dataset.kind}"]`).forEach(flow => flow.classList.toggle('off', !on));
    }));
    const motion = root.querySelector('.fig-motion');
    motion?.addEventListener('click', () => {
      const paused = !root.classList.contains('paused');
      root.classList.toggle('paused', paused);
      motion.setAttribute('aria-pressed', String(paused));
      motion.textContent = paused ? t('Play motion', 'Chạy chuyển động') : t('Pause motion', 'Dừng chuyển động');
    });
    const select = slot => {
      const item = root.querySelector(`.fig-parts [data-slot="${slot}"]`), already = item?.classList.contains('active');
      root.querySelectorAll('.fig-parts li, .ap-callout').forEach(node => node.classList.remove('active'));
      if (!already) root.querySelectorAll(`[data-slot="${slot}"]`).forEach(node => node.classList.add('active'));
    };
    root.querySelectorAll('.fig-part').forEach(button => button.addEventListener('click', () => select(button.closest('li').dataset.slot)));
    root.querySelectorAll('.ap-callout').forEach(callout => callout.addEventListener('click', () => select(callout.dataset.slot)));
  }

  /* What-if: raise or lower a setting and follow the directions the source states. */
  function whatIf(root, spec) {
    const grid = root.querySelector('.fig-effects'), links = root.querySelector('.fig-links'), announce = root.querySelector('.fig-announce');
    const nodes = new Map([...root.querySelectorAll('.fig-node')].map(node => [node.dataset.node, node]));
    const choice = new Map();
    const name = id => nodes.get(id)?.querySelector('strong').textContent || id;
    function propagate() {
      const reached = new Map(), edges = new Set();
      for (const [lever, sign] of choice) {
        const seen = new Set(), queue = [[lever, sign]];
        while (queue.length) {
          const [id, s] = queue.shift();
          if (seen.has(id + s)) continue;
          seen.add(id + s);
          if (!reached.has(id)) reached.set(id, new Set());
          reached.get(id).add(s);
          spec.effects.forEach((effect, k) => { if (effect.source === id) { edges.add(k); queue.push([effect.target, s * effect.sign]); } });
        }
      }
      return {reached, edges};
    }
    function draw() {
      const {edges} = propagate(), scale = scaleOf(grid), box = grid.getBoundingClientRect();
      links.replaceChildren();
      if (getComputedStyle(links).display === 'none') return;
      spec.effects.forEach((effect, k) => {
        const a = nodes.get(effect.source)?.getBoundingClientRect(), b = nodes.get(effect.target)?.getBoundingClientRect();
        if (!a || !b) return;
        const local = (value, origin) => (value - origin) / scale;
        let x1 = local(a.right, box.left), y1 = local(a.top + a.height / 2, box.top), x2 = local(b.left, box.left), y2 = local(b.top + b.height / 2, box.top);
        let d;
        const skip = Number(nodes.get(effect.target).dataset.column) - Number(nodes.get(effect.source).dataset.column) > 1;
        if (skip) {
          // An effect that skips a column runs under the cards between, not through them.
          const under = local(box.bottom, box.top) - 14, middle = (x1 + x2) / 2;
          d = `M ${x1} ${y1} C ${x1 + 30} ${y1}, ${middle - 60} ${under}, ${middle} ${under} S ${x2 - 30} ${y2}, ${x2 - 4} ${y2}`;
        } else if (x2 > x1 + 8) d = `M ${x1} ${y1} C ${(x1 + x2) / 2} ${y1}, ${(x1 + x2) / 2} ${y2}, ${x2 - 4} ${y2}`;
        else { // same column or backwards: loop around the right side
          x2 = local(b.right, box.left);
          const out = Math.max(x1, x2) + 34;
          d = `M ${x1} ${y1} C ${out} ${y1}, ${out} ${y2}, ${x2 + 4} ${y2}`;
        }
        const path = svg('path', {d, class: `fig-link${edges.has(k) ? ' active' : ''}`}, links);
        const middle = path.getPointAtLength(path.getTotalLength() / 2), sign = svg('g', {class: 'fig-sign'}, links);
        svg('circle', {cx: middle.x, cy: middle.y, r: 9}, sign);
        svg('text', {x: middle.x, y: middle.y + 4}, sign, effect.sign > 0 ? '+' : '−');
      });
    }
    function update() {
      const {reached} = propagate();
      for (const [id, node] of nodes) {
        const signs = reached.get(id), label = node.querySelector('.fig-node-state');
        let state = '';
        if (choice.has(id)) state = choice.get(id) > 0 ? 'up' : 'down';
        else if (signs) state = signs.size > 1 ? 'mixed' : signs.has(1) ? 'up' : 'down';
        node.dataset.state = state;
        label.textContent = !state ? '' : choice.has(id) ? (state === 'up' ? t('↑ raised', '↑ đã tăng') : t('↓ lowered', '↓ đã giảm'))
          : {up: t('↑ rises', '↑ tăng'), down: t('↓ falls', '↓ giảm'), mixed: t('↕ depends on which effect is stronger', '↕ tùy tác động nào mạnh hơn')}[state];
      }
      root.querySelectorAll('.fig-lever button').forEach(button => button.setAttribute('aria-pressed', String(choice.get(button.closest('.fig-lever').dataset.lever) === Number(button.dataset.sign))));
      const changed = [...reached.keys()].filter(id => !choice.has(id)).map(id => `${name(id)} ${nodes.get(id).querySelector('.fig-node-state').textContent}`);
      announce.textContent = choice.size ? [...choice].map(([id, s]) => `${name(id)} ${s > 0 ? t('raised', 'tăng') : t('lowered', 'giảm')}`).join(', ') + (changed.length ? ': ' + changed.join('; ') : '') : '';
      draw();
    }
    root.querySelectorAll('.fig-lever button').forEach(button => button.addEventListener('click', () => {
      const lever = button.closest('.fig-lever').dataset.lever, sign = Number(button.dataset.sign);
      if (choice.get(lever) === sign) choice.delete(lever); else choice.set(lever, sign);
      update();
    }));
    root.querySelector('.fig-reset').addEventListener('click', () => { choice.clear(); update(); });
    observe(grid, draw);
    update();
  }

  const builders = {process, region_map: regionMap, apparatus, what_if: whatIf};
  document.querySelectorAll('.figure[data-figure]').forEach(root => {
    const build = builders[root.dataset.figure], data = root.querySelector('script.figure-data');
    if (!build) return;
    try { build(root, data ? JSON.parse(data.textContent) : {}); } catch (error) { console.error('Figure could not be drawn', error); }
  });
})();
