"""Process figures: escaped server HTML, plus a JSON spec that figures.js draws at the real width.

Server HTML carries everything a reader needs without script: state cards, numbered parts,
effect lists and data tables. Script adds the charts, the time scrubber, layers and levers.
"""
from __future__ import annotations

import html
import json

from .apparatus import TEMPLATES
from .models import Figure, FigurePlan, KnowledgeModel, figure_unit_ids

e = html.escape
BEAN_COLOURS = ("#8fa66a", "#cdb46a", "#a8743f", "#6e4427", "#3b2417")


def _json(data) -> str:
    return json.dumps(data, ensure_ascii=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def _number(value: float, vi: bool = False) -> str:
    text = f"{value:.0f}" if abs(value) >= 100 or value == int(value) else f"{value:.2f}".rstrip("0").rstrip(".")
    return text.replace(".", ",") if vi else text


def figure_ideas(figure: Figure) -> list[str]:
    """The figure's own ideas first, then every other idea its elements cite."""
    return list(dict.fromkeys([*figure.unit_ids, *sorted(figure_unit_ids(figure) - set(figure.unit_ids))]))


class FigureContext:
    def __init__(self, knowledge: KnowledgeModel, mode: str):
        self.vi = knowledge.language == "vi"
        self.mode = mode
        self.units = {u.id: u for u in knowledge.units}
        self.relationships = {r.id: r for r in knowledge.relationships}

    def t(self, en, vn):
        return vn if self.vi else en

    def clock(self, seconds: float) -> str:
        seconds = int(round(seconds))
        sign = "-" if seconds < 0 else ""
        seconds = abs(seconds)
        return f"{sign}{seconds // 60}:{seconds % 60:02d}"

    def at(self, spec, value: float) -> str:
        if spec.axis == "time":
            return self.clock(value)
        return f"{_number(value, self.vi)} {e(spec.axis_unit)}".strip()

    def chips(self, ids) -> str:
        if self.mode != "page" or not ids:
            return ""
        buttons = "".join(f'<button type="button" class="fig-unit" data-select-unit="{e(uid)}">{e(self.units[uid].title)}</button>'
                          for uid in dict.fromkeys(ids) if uid in self.units)
        return f'<p class="fig-sources"><span>{self.t("Based on", "Dựa trên")}</span> {buttons}</p>'

    def badges(self, figure: Figure) -> str:
        statuses = {self.units[uid].status for uid in figure_unit_ids(figure) if uid in self.units}
        labels = {"inference": self.t("Includes inference", "Có suy luận"), "uncertain": self.t("Includes uncertain points", "Có điểm chưa chắc chắn"),
                  "background": self.t("Includes added background", "Có kiến thức bổ sung")}
        provenance = set()
        if figure.process:
            provenance = {series.provenance for series in figure.process.series}
        elif figure.region_map:
            provenance = {figure.region_map.provenance}
        values = {"source": self.t("Values stated in the source", "Số liệu theo nguồn"),
                  "background": self.t("Reference values, not from the source", "Số liệu tham khảo, không có trong nguồn"),
                  "illustrative": self.t("Illustrative shape: no real values", "Hình dáng minh họa: không phải số liệu thật")}
        marks = [f'<span class="status-badge fig-badge {name}">{label}</span>' for name, label in labels.items() if name in statuses]
        marks += [f'<span class="fig-badge provenance-{name}">{label}</span>' for name, label in values.items() if name in provenance]
        if figure.what_if:
            marks.append(f'<span class="fig-badge provenance-illustrative">{self.t("Direction only, not size", "Chỉ chiều tăng giảm, không phải mức độ")}</span>')
        return f'<div class="fig-badges">{"".join(marks)}</div>' if marks else ""


def meter(level: int, label: str) -> str:
    pips = "".join(f'<i class="{"on" if index < level else ""}"></i>' for index in range(4))
    return f'<span class="fig-meter" role="img" aria-label="{e(label)}: {level}/4">{pips}</span>'


def glyph(subject: str, properties) -> str:
    """A small schematic of the subject in one state; known property keys change the drawing."""
    level = {p.key: p.level for p in properties}
    parts = []
    if subject == "bean":
        scale = .82 + .06 * level.get("volume", 1)
        colour = BEAN_COLOURS[level.get("color", 1)]
        for index in range(level.get("moisture", 0)):
            x, y = 20 + index * 9, 22 + (index % 2) * 8
            parts.append(f'<path class="glyph-water" d="M {x} {y - 7} C {x - 5} {y}, {x - 4} {y + 4}, {x} {y + 4} C {x + 4} {y + 4}, {x + 5} {y}, {x} {y - 7} Z"/>')
        bean = (f'<g transform="translate(64 64) rotate(-20) scale({scale:.2f})"><ellipse class="glyph-bean" style="fill:{colour}" rx="32" ry="42"/>'
                '<path class="glyph-crease" d="M 0 -36 C -12 -18, 12 -6, 0 8 S -10 28, 0 36"/>')
        for index in range(level.get("cracks", 0)):
            y = -24 + index * 15
            bean += f'<path class="glyph-crack" d="M 30 {y} l -9 3 l 4 4 l -8 3"/>'
        for index in range(level.get("oil", 0)):
            bean += f'<ellipse class="glyph-oil" cx="{-14 + index * 6}" cy="{-20 + index * 12}" rx="4" ry="2.2"/>'
        for index in range(level.get("porosity", 0) * 3):
            bean += f'<circle class="glyph-pore" cx="{-18 + (index * 13) % 34}" cy="{-26 + (index * 17) % 54}" r="1.8"/>'
        if level.get("pressure", 0):
            bean += '<ellipse class="glyph-pressure" rx="20" ry="27"/>'
            for index in range(level["pressure"]):
                angle = index * 90 + 45
                bean += f'<path class="glyph-push" d="M 0 0 L 0 -20" transform="rotate({angle}) translate(0 -8)"/>'
        parts.append(bean + "</g>")
    elif subject == "particle":
        dissolved = level.get("dissolved", 0)
        if level.get("moisture", 0):
            parts.append(f'<circle class="glyph-halo" cx="64" cy="64" r="54" style="opacity:{.15 + .12 * level["moisture"]:.2f}"/>')
        shape = "M 64 22 L 94 34 L 104 66 L 88 98 L 54 104 L 28 84 L 24 50 Z"
        parts.append(f'<path class="glyph-grounds" d="{shape}"/>')
        core = 1 - dissolved * .2
        parts.append(f'<path class="glyph-solubles" d="{shape}" transform="translate(64 64) scale({core:.2f}) translate(-64 -64)"/>')
        for index in range(dissolved * 2):
            x, y = 14 + (index * 29) % 100, 14 + (index * 47) % 100
            parts.append(f'<circle class="glyph-solute" cx="{x}" cy="{y}" r="3"/>')
    else:
        first = properties[0].level if properties else 0
        parts.append(f'<rect class="glyph-generic" x="24" y="24" width="80" height="80" rx="18" style="opacity:{.3 + .17 * first:.2f}"/>')
    return f'<svg class="fig-glyph" viewBox="0 0 128 128" aria-hidden="true">{"".join(parts)}</svg>'


def _table(head, rows, caption) -> str:
    return (f'<div class="fig-table-scroll"><table class="fig-data"><caption>{e(caption)}</caption><thead><tr>'
            + "".join(f'<th scope="col">{e(cell)}</th>' for cell in head) + "</tr></thead><tbody>"
            + "".join("<tr>" + "".join(f"<td>{e(str(cell))}</td>" for cell in row) + "</tr>" for row in rows)
            + "</tbody></table></div>")


def _process(figure: Figure, ctx: FigureContext, number: int) -> dict:
    spec = figure.process
    t = ctx.t
    chips = "".join(f'<button type="button" data-phase="{e(p.id)}" aria-pressed="false">{e(p.label)}</button>' for p in spec.phases)
    glyph_states = {state.phase_id: state for state in spec.states}
    # Phases in order only, with no unit: positions carry no value, so no numbers are shown for them.
    ordinal = spec.axis != "time" and not spec.axis_unit
    span = lambda phase: "" if ordinal else f" · {ctx.at(spec, phase.start)}–{ctx.at(spec, phase.end)}"
    cards = []
    for index, phase in enumerate(spec.phases, 1):
        state = glyph_states.get(phase.id)
        if not state:
            continue
        rows = "".join(f'<li><span class="fig-prop-label">{e(p.label)}</span>{meter(p.level, p.label)}'
                       f'<span class="fig-prop-text">{e(p.text)}</span></li>' for p in state.properties)
        cards.append(f'<article role="listitem" class="fig-state" data-phase="{e(phase.id)}">{glyph(spec.subject, state.properties)}'
                     f'<div><p class="fig-state-time">{index:02d}{span(phase)}</p>'
                     f'<h3>{e(phase.label)}</h3><p>{e(state.caption)}</p><ul class="fig-props">{rows}</ul></div></article>')
    states = f'<div class="fig-states" role="list" aria-label="{e(spec.subject_label)}">{"".join(cards)}</div>' if cards else ""
    unit = lambda s: f" ({s.unit})" if s.unit else ""
    if ordinal:
        tables = [_table([t("Phase", "Giai đoạn"), t("What happens", "Diễn biến")], [(p.label, p.note) for p in spec.phases], t("Phases", "Các giai đoạn"))]
    else:
        tables = [_table([t("Phase", "Giai đoạn"), t("From", "Từ"), t("To", "Đến"), t("What happens", "Diễn biến")],
                         [(p.label, ctx.at(spec, p.start), ctx.at(spec, p.end), p.note) for p in spec.phases], t("Phases", "Các giai đoạn"))]
    if spec.events and not ordinal:
        tables.append(_table([t("Event", "Mốc"), t("At", "Tại")], [(ev.label, ctx.at(spec, ev.at)) for ev in spec.events], t("Events", "Các mốc")))
    for series in spec.series:
        if series.provenance == "illustrative":
            continue
        tables.append(_table([spec.axis_label, series.label + unit(series)], [(ctx.at(spec, p.x), _number(p.y, ctx.vi)) for p in series.points],
                             series.label + (t(" · stated in the source", " · theo nguồn") if series.provenance == "source" else t(" · reference values", " · số liệu tham khảo"))))
    grid = ""
    if spec.compounds:
        head = "".join(f'<th scope="col" data-phase="{e(p.id)}">{e(p.label)}</th>' for p in spec.phases)
        rows = "".join(f'<tr><th scope="row">{e(lane.name)}</th>' + "".join(f'<td data-phase="{e(p.id)}">{meter(level, lane.name)}</td>'
                       for p, level in zip(spec.phases, lane.levels)) + "</tr>" for lane in spec.compounds)
        grid = (f'<div class="fig-table-scroll"><table class="fig-compounds"><caption>{t("Relative amounts in each phase", "Lượng tương đối ở mỗi giai đoạn")}</caption>'
                f'<thead><tr><td></td>{head}</tr></thead><tbody>{rows}</tbody></table></div>')
        tables.append(_table([t("Compound", "Hợp chất"), *[p.label for p in spec.phases]],
                             [(lane.name, *[f"{level}/4" for level in lane.levels]) for lane in spec.compounds],
                             t("Relative amount in each phase (0 none – 4 very high)", "Lượng tương đối ở mỗi giai đoạn (0 không có – 4 rất nhiều)")))
    data = {"axis": spec.axis, "axis_label": spec.axis_label, "axis_unit": spec.axis_unit,
            "phases": [p.model_dump(include={"id", "label", "start", "end", "note"}) for p in spec.phases],
            "events": [ev.model_dump(include={"at", "label"}) for ev in spec.events],
            "series": [s.model_dump(include={"id", "label", "unit", "provenance", "points"}) for s in spec.series],
            "compounds": [lane.model_dump(include={"name", "levels", "note"}) for lane in spec.compounds]}
    low, high = spec.phases[0].start, spec.phases[-1].end
    log_name = {"bean": t("Compare a roast log", "So với log rang của bạn"), "particle": t("Compare a shot log", "So với log chiết của bạn")}.get(
        spec.subject, t("Compare a data log", "So với dữ liệu của bạn"))
    log = (f'<button type="button" class="fig-log" data-label="{e(log_name)}">{log_name}</button>'
           f'<input type="file" class="fig-log-file" accept=".alog,.csv,.txt,.tsv" hidden>'
           f'<span class="fig-log-status" aria-live="polite"></span>') if spec.axis == "time" and ctx.mode == "page" else ""
    # Without curves (and, on a slide, without lanes) the chart is only the phase band.
    compact = not spec.series and (ctx.mode == "slide" or not spec.compounds)
    controls = (f'<div class="fig-phases" role="group" aria-label="{t("Phases", "Các giai đoạn")}">{chips}</div>'
                f'<div class="fig-chart{" compact" if compact else ""}" aria-hidden="true"></div>'
                f'<div class="fig-controls"><label class="fig-scrub-label" for="scrub-{number}">{e(spec.axis_label)}</label>'
                f'<input id="scrub-{number}" class="fig-scrubber" type="range" min="{low}" max="{high}" step="{(high - low) / 400:.4f}" value="{low}">'
                f'<button type="button" class="fig-play" aria-pressed="false">{t("Play", "Chạy")}</button>{log}</div>'
                f'<p class="fig-readout"></p><p class="fig-announce sr-only" role="status" aria-live="polite"></p>')
    details = f'<details class="fig-table"><summary>{t("Figure data", "Dữ liệu của hình")}</summary>{"".join(tables)}</details>'
    script = f'<script type="application/json" class="figure-data">{_json(data)}</script>'
    if ctx.mode == "slide":
        # A slide has no room for lanes under the curves: compounds move to the states slide as a phase grid.
        slide_script = f'<script type="application/json" class="figure-data">{_json(data | {"compounds": []})}</script>'
        if compact:
            # Only the phase band to show: the states and compounds share its slide.
            return {"slides": [{"title": figure.title, "content": f'<div class="figure fig-slide" data-figure="process" data-key="fig{number}">'
                                f'{ctx.badges(figure)}{controls}{states}{grid}{slide_script}</div>'}]}
        slides = [{"title": figure.title, "content": f'<div class="figure fig-slide" data-figure="process" data-key="fig{number}">{ctx.badges(figure)}{controls}{slide_script}</div>'}]
        if states or grid:
            title = (t(f"How the {spec.subject_label.lower()} changes", f"{spec.subject_label} thay đổi thế nào") if states
                     else t("Compounds through the phases", "Các hợp chất qua từng giai đoạn"))
            slides.append({"title": title, "content": f'<div class="figure fig-slide fig-slide-states" data-figure="process-states" data-key="fig{number}">{states}{grid}</div>'})
        return {"slides": slides}
    body = f'{ctx.badges(figure)}{controls}{states}{details}{ctx.chips(figure_ideas(figure))}{script}'
    return {"body": f'<div class="figure" data-figure="process" data-key="fig{number}">{body}</div>'}


FLOW_NAMES = {"conduction": ("Conduction", "Dẫn nhiệt"), "convection": ("Convection", "Đối lưu"), "radiation": ("Radiation", "Bức xạ"),
              "air": ("Air", "Không khí"), "water": ("Water", "Nước"), "gas": ("Steam / gas", "Hơi / khí"),
              "pressure": ("Pressure", "Áp suất"), "material": ("Material", "Vật chất")}


def _apparatus(figure: Figure, ctx: FigureContext, number: int) -> dict:
    spec = figure.apparatus
    template = TEMPLATES[spec.template]
    t = ctx.t
    prefix = f"fig{number}"
    kinds = list(dict.fromkeys(flow.kind for flow in spec.flows))
    markers = "".join(f'<marker id="{prefix}-arrow-{kind}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">'
                      f'<path class="marker-{kind}" d="M 0 0 L 10 5 L 0 10 z"/></marker>' for kind in kinds)
    flows = []
    for flow in spec.flows:
        paths = "".join(f'<path class="flow-line" d="{d}" marker-end="url(#{prefix}-arrow-{flow.kind})"/>' for d in template["paths"][flow.path]["d"])
        flows.append(f'<g class="flow flow-{flow.kind}" data-kind="{flow.kind}" data-path="{e(flow.path)}"><title>{e(flow.label)}</title>{paths}</g>')
    callouts = []
    for index, part in enumerate(spec.parts, 1):
        slot = template["slots"][part.slot]
        x, y = slot["at"]
        leader = f'<line class="ap-leader" x1="{x}" y1="{y}" x2="{slot["to"][0]}" y2="{slot["to"][1]}"/>' if "to" in slot else ""
        callouts.append(f'<g class="ap-callout" data-slot="{e(part.slot)}">{leader}<circle cx="{x}" cy="{y}" r="15"/>'
                        f'<text x="{x}" y="{y}" dy=".35em">{index}</text></g>')
    title_id, desc_id = f"{prefix}-title", f"{prefix}-desc"
    description = "; ".join(f"{index}. {part.label}" for index, part in enumerate(spec.parts, 1))
    drawing = (f'<svg class="ap-svg" viewBox="0 0 800 500" role="img" aria-labelledby="{title_id} {desc_id}">'
               f'<title id="{title_id}">{e(figure.title)}</title><desc id="{desc_id}">{e(description)}</desc>'
               f'<defs>{markers}</defs><g class="ap-drawing">{template["draw"]()}</g><g class="ap-flows">{"".join(flows)}</g>'
               f'<g class="ap-callouts">{"".join(callouts)}</g></svg>')
    layers = "".join(f'<button type="button" class="fig-layer" data-kind="{kind}" aria-pressed="true"><span class="fig-key key-{kind}" aria-hidden="true"></span>'
                     f'{t(*FLOW_NAMES[kind])}</button>' for kind in kinds)
    motion = f'<button type="button" class="fig-motion" aria-pressed="false">{t("Pause motion", "Dừng chuyển động")}</button>' if kinds else ""
    toolbar = f'<div class="fig-layers" role="group" aria-label="{t("Show flows", "Hiện dòng chảy")}">{layers}{motion}</div>' if kinds else ""
    full = ctx.mode == "page"
    parts = "".join(f'<li data-slot="{e(part.slot)}"><button type="button" class="fig-part">{e(part.label)}</button>'
                    + (f'<p>{e(part.note)}</p>' if full and part.note else "") + "</li>" for part in spec.parts)
    flow_list = "".join(f'<li><span class="fig-key key-{flow.kind}" aria-hidden="true"></span><span><b>{e(flow.label)}</b>'
                        f' · {t(*FLOW_NAMES[flow.kind])}</span></li>' for flow in spec.flows)
    legend = (f'<div class="fig-legend"><ol class="fig-parts">{parts}</ol>'
              + (f'<ul class="fig-flows">{flow_list}</ul>' if flow_list and full else "") + "</div>")
    body = f'{ctx.badges(figure)}{toolbar}<div class="fig-apparatus"><div class="fig-drawing">{drawing}</div>{legend}</div>'
    if ctx.mode == "slide":
        return {"slides": [{"title": figure.title, "content": f'<div class="figure fig-slide" data-figure="apparatus">{body}</div>'}]}
    return {"body": f'<div class="figure" data-figure="apparatus">{body}{ctx.chips(figure_ideas(figure))}</div>'}


def _region_map(figure: Figure, ctx: FigureContext, number: int) -> dict:
    spec = figure.region_map
    t = ctx.t
    unit = lambda value, name: f"{_number(value, ctx.vi)} {name}".strip()
    regions = "".join(f'<li data-region="{index}" class="{"emphasis" if region.emphasis else ""}"><button type="button" class="fig-region-button">'
                      f'<b>{index}</b> {e(region.label)}</button>' + (f'<p>{e(region.note)}</p>' if region.note and ctx.mode == "page" else "")
                      + "</li>" for index, region in enumerate(spec.regions, 1))
    rows = [(region.label, f"{unit(region.x_min, spec.x_unit)} – {unit(region.x_max, spec.x_unit)}",
             f"{unit(region.y_min, spec.y_unit)} – {unit(region.y_max, spec.y_unit)}") for region in spec.regions]
    rows += [(point.label, unit(point.x, spec.x_unit), unit(point.y, spec.y_unit)) for point in spec.points]
    table = (f'<details class="fig-table"><summary>{t("Figure data", "Dữ liệu của hình")}</summary>'
             + _table([t("Region or point", "Vùng hoặc điểm"), spec.x_label, spec.y_label], rows, figure.title) + "</details>"
             if spec.provenance != "illustrative" else "")
    data = spec.model_dump(exclude={"regions", "points"}) | {
        "regions": [r.model_dump(include={"label", "x_min", "x_max", "y_min", "y_max", "emphasis"}) for r in spec.regions],
        "points": [p.model_dump(include={"label", "x", "y"}) for p in spec.points]}
    body = (f'{ctx.badges(figure)}<div class="fig-map"><div class="fig-chart" aria-hidden="true"></div><ol class="fig-regions">{regions}</ol></div>'
            f'{table if ctx.mode == "page" else ""}<script type="application/json" class="figure-data">{_json(data)}</script>')
    if ctx.mode == "slide":
        return {"slides": [{"title": figure.title, "content": f'<div class="figure fig-slide" data-figure="region_map">{body}</div>'}]}
    return {"body": f'<div class="figure" data-figure="region_map">{body}{ctx.chips(figure_ideas(figure))}</div>'}


def _what_if(figure: Figure, ctx: FigureContext, number: int) -> dict:
    spec = figure.what_if
    t = ctx.t
    effects = [(ctx.relationships[effect.relationship_id], effect.direction) for effect in spec.effects]
    # Columns by the longest chain from a lever, at most four, so each idea sits after its causes.
    # The cap ends the relaxation when the effects form a loop.
    levers_ids = {lever.unit_id for lever in spec.levers}
    depth = {uid: 0 for uid in levers_ids}
    for _ in range(len(effects) + 1):
        changed = False
        for relationship, _direction in effects:
            if relationship.source in depth and relationship.target not in levers_ids:
                proposed = min(3, depth[relationship.source] + 1)
                if proposed > depth.get(relationship.target, -1):
                    depth[relationship.target] = proposed
                    changed = True
        if not changed:
            break
    for relationship, _direction in effects:
        depth.setdefault(relationship.source, 0)
        depth.setdefault(relationship.target, min(3, depth[relationship.source] + 1))
    columns = [[uid for uid in depth if depth[uid] == level] for level in range(max(depth.values()) + 1)]
    lever_names = {lever.unit_id: lever.label for lever in spec.levers}
    levers = "".join(f'<div class="fig-lever" data-lever="{e(lever.unit_id)}"><span>{e(lever.label)}</span>'
                     f'<button type="button" data-sign="1" aria-pressed="false">↑ {t("Raise", "Tăng")}</button>'
                     f'<button type="button" data-sign="-1" aria-pressed="false">↓ {t("Lower", "Giảm")}</button></div>' for lever in spec.levers)
    def node(uid):
        unit = ctx.units[uid]
        label = lever_names.get(uid, unit.title)
        select = f' data-select-unit="{e(uid)}"' if ctx.mode == "page" else ""
        tag = "button type=\"button\"" if ctx.mode == "page" else "div"
        close = "button" if ctx.mode == "page" else "div"
        return (f'<{tag} class="fig-node{" is-lever" if uid in lever_names else ""}" data-node="{e(uid)}" data-column="{depth[uid]}"{select}>'
                f'<strong>{e(label)}</strong><span class="fig-node-state"></span></{close}>')
    grid = "".join(f'<div class="fig-column">{"".join(node(uid) for uid in column)}</div>' for column in columns if column)
    arrow = {"increases": "↑", "decreases": "↓"}
    status_names = {"inference": t("Inference", "Suy luận"), "uncertain": t("Uncertain", "Chưa chắc chắn"),
                    "background": t("Added background", "Kiến thức bổ sung")}
    def effect_line(relationship, direction):
        badge = (f' <span class="status-badge {relationship.status}">{status_names[relationship.status]}</span>'
                 if relationship.status in status_names else "")
        return (f'<li><b>{e(lever_names.get(relationship.source, ctx.units[relationship.source].title))}</b> ↑ → '
                f'<b>{e(ctx.units[relationship.target].title)}</b> {arrow[direction]}<span class="muted"> · {e(relationship.label)}</span>{badge}</li>')
    listing = "".join(effect_line(r, d) for r, d in effects)
    data = {"effects": [{"source": r.source, "target": r.target, "sign": 1 if d == "increases" else -1} for r, d in effects]}
    body = (f'{ctx.badges(figure)}<div class="fig-levers" role="group" aria-label="{t("Settings", "Thông số")}">{levers}'
            f'<button type="button" class="fig-reset">{t("Reset", "Đặt lại")}</button></div>'
            f'<div class="fig-effects" style="--columns:{len([c for c in columns if c])}"><svg class="fig-links" aria-hidden="true"></svg>{grid}</div>'
            f'<p class="fig-announce" role="status" aria-live="polite"></p>'
            f'<details class="fig-table"{" open" if ctx.mode == "slide" else ""}><summary>{t("Effects stated in the source", "Các tác động theo nguồn")}</summary><ul class="fig-effect-list">{listing}</ul></details>'
            f'<script type="application/json" class="figure-data">{_json(data)}</script>')
    if ctx.mode == "slide":
        return {"slides": [{"title": figure.title, "content": f'<div class="figure fig-slide" data-figure="what_if">{body}</div>'}]}
    return {"body": f'<div class="figure" data-figure="what_if">{body}{ctx.chips(figure_ideas(figure))}</div>'}


def _scale_ladder(figure: Figure, ctx: FigureContext, number: int) -> dict:
    levels = figure.scale_ladder.levels
    items = "".join(f'<li class="fig-level" style="--level:{index}"><span class="fig-lens-box" aria-hidden="true"><span class="fig-lens"></span></span>'
                    f'<p class="fig-scale">{e(level.scale)}</p><h3>{e(level.title)}</h3><p>{e(level.summary)}</p></li>'
                    for index, level in enumerate(levels))
    body = f'{ctx.badges(figure)}<ol class="fig-ladder" style="--levels:{len(levels)}">{items}</ol>'
    if ctx.mode == "slide":
        return {"slides": [{"title": figure.title, "content": f'<div class="figure fig-slide" data-figure="scale_ladder">{body}</div>'}]}
    return {"body": f'<div class="figure" data-figure="scale_ladder">{body}{ctx.chips(figure_ideas(figure))}</div>'}


BUILDERS = {"process": _process, "apparatus": _apparatus, "region_map": _region_map, "what_if": _what_if, "scale_ladder": _scale_ladder}


def figure_sections(knowledge: KnowledgeModel, plan: FigurePlan | None) -> str:
    """Page sections; reader.js moves them after the learning views and links them in the view menu."""
    if not plan or not plan.figures:
        return ""
    ctx = FigureContext(knowledge, "page")
    sections = []
    for number, figure in enumerate(plan.figures, 1):
        built = BUILDERS[figure.type](figure, ctx, number)
        caption = f'<p class="fig-caption">{e(figure.caption)}</p>' if figure.caption else ""
        sections.append(f'<section class="visual-section figure-section" id="figure-{number}" data-figure-type="{figure.type}" data-title="{e(figure.title)}">'
                        f'<div class="section-heading"><p class="eyebrow">{ctx.t("FIGURE", "HÌNH")} {number:02d} / {ctx.t("EXPLORE", "KHÁM PHÁ")}</p>'
                        f'<h2>{e(figure.title)}</h2><p>{e(figure.reader_question)}</p></div>{caption}{built["body"]}</section>')
    return f'<div id="process-figures">{"".join(sections)}</div>'


def figure_slides(knowledge: KnowledgeModel, figure: Figure, number: int) -> list[dict]:
    return BUILDERS[figure.type](figure, FigureContext(knowledge, "slide"), number)["slides"]
