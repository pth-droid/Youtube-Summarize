"""Slide layouts for lecture decks, from the slide-design layout library (layouts.css and data.css in reader_assets).

The model writes content only. For each slide this module lists the library layouts the content fits, within
the library's character limits, and writes the library's markup. `arrange` then picks one layout and variant
per slide by rotation, so a deck never shows the same frame twice in a row (LAYOUTS.md, "Rotation").

Markup conventions: `data-part` orders the arrival stagger (0 is the title); `data-build` marks the items a
presenter reveals one advance at a time. The first item of a list always arrives with the slide.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Callable

e = html.escape
VARIANTS = (1, 2, 3, 4)
# The library's limits are for full-size type; .dense and .denser give about 20-35% more room before text shrinks.
ROOM = 1.25
# Full-surface fills: never two in a row (LAYOUTS.md, rotation rule 3).
HEAVY = {("title", 1), ("section", 1), ("section", 3), ("quote", 2)}
ACCENTS = ("accent-left", "accent-right-fit", "accent-top", "accent-right", "accent-left-fit")


@dataclass
class Choice:
    layout: str
    variants: tuple
    build: Callable[[], str]
    heading: str | None = None  # replaces the slide's <h2> (covers use <h1>; quotes set a short context)


def fits(values, limit):
    return all(len(value) <= limit * ROOM for value in values)


def labelled(text, limit):
    """'Label: text' as (label, text) when the label is short, else None. Clock times such as 10:30 are not labels."""
    head, sep, tail = text.partition(":")
    head, tail = head.strip(), tail.strip()
    if not sep or not head or not tail or len(head) > limit or (head[-1:].isdigit() and tail[:1].isdigit()):
        return None
    return head, tail


def pairs_of(values, limit):
    pairs = [labelled(value, limit) for value in values]
    return pairs if all(pairs) else None


def part(index):
    return f' data-part="{min(index + 1, 6)}"' + (" data-build" if index else "")


def items(values, cls, tag="ul", raw=False):
    body = "".join(f"<li{part(k)}>{value if raw else e(value)}</li>" for k, value in enumerate(values))
    return f'<{tag} class="{cls}">{body}</{tag}>'


def plain(values):
    """A column body: one paragraph, or a dash list for several points."""
    if len(values) == 1:
        return f"<p>{e(values[0])}</p>"
    return "<ul>" + "".join(f"<li>{e(value)}</li>" for value in values) + "</ul>"


def cols(blocks):
    """blocks: (heading or None, body html)."""
    return '<div class="cols">' + "".join(
        f'<div class="col"{part(k)}>' + (f"<h3>{e(head)}</h3>" if head else "") + body + "</div>"
        for k, (head, body) in enumerate(blocks)) + "</div>"


def boxes(rows, cls="boxes"):
    return f'<ul class="{cls}">' + "".join(f"<li{part(k)}><h3>{e(head)}</h3><p>{e(text)}</p></li>" for k, (head, text) in enumerate(rows)) + "</ul>"


def icons(rows):
    # A mono ordinal stands in for an icon: the library accepts one to three characters in a glyph badge.
    return '<ul class="icons">' + "".join(
        f'<li{part(k)}><span class="glyph" aria-hidden="true">{k + 1:02d}</span><h3>{e(head)}</h3><p>{e(text)}</p></li>'
        for k, (head, text) in enumerate(rows)) + "</ul>"


def small_icons(values):
    return '<ul class="small-icons">' + "".join(
        f'<li{part(k)}><span class="glyph" aria-hidden="true">{k + 1:02d}</span><p>{e(value)}</p></li>'
        for k, value in enumerate(values)) + "</ul>"


def timeline(rows):
    """rows: (time, heading or None, text or None)."""
    return '<ol class="timeline">' + "".join(
        f"<li{part(k)}><time>{e(when)}</time>" + (f"<h3>{e(head)}</h3>" if head else "") + (f"<p>{e(text)}</p>" if text else "") + "</li>"
        for k, (when, head, text) in enumerate(rows)) + "</ol>"


def arrows(rows):
    return '<ol class="arrows">' + "".join(
        f"<li{part(k)}><h3>{e(head)}</h3>" + (f"<p>{e(text)}</p>" if text else "") + "</li>" for k, (head, text) in enumerate(rows)) + "</ol>"


def accent(label, statement, rest):
    body = ("<ul>" + "".join(f"<li{part(k + 1)}>{e(value)}</li>" for k, value in enumerate(rest)) + "</ul>") if rest else ""
    return (f'<div class="accent" data-part="1"><p class="accent-label">{e(label)}</p><p class="accent-statement">{e(statement)}</p></div>'
            f'<div class="body">{body}</div>')


def levels(rows):
    return '<ol class="levels">' + "".join(
        f'<li{part(k)}><span class="level-label">{e(head)}</span><span class="level-note">{e(text)}</span></li>'
        for k, (head, text) in enumerate(rows)) + "</ol>"


FIGURE = re.compile(r"^\s*([−\-+]?\d[\d.,\s]*(?:[–-]\s?\d[\d.,]*)?)\s*(.*?)\s*$")


def figure(label):
    """A stated figure as (value, unit), e.g. '18–22%' -> ('18–22', '%'), or None."""
    match = FIGURE.match(label)
    return (match.group(1).strip(), match.group(2)) if match else None


def number(value):
    try:
        return float(value.replace(" ", "").replace(",", ".").replace("−", "-"))
    except ValueError:
        return None


# ---------- What each kind of content fits ----------

def point_choices(heading, points, t):
    n = len(points)
    # Rows of bullets hold anything, so they are always a choice; shorter lists also fit the others.
    choices = [Choice("bullets", VARIANTS if fits(points, 64) else (1, 2, 3), lambda: items(points, "bullets"))]
    if 2 <= n <= 4 and fits(points, 56):
        choices.append(Choice("big-bullets", (1, 2, 3), lambda: items(points, "big-list", "ol")))
    if n == 2 and fits(points, 200):
        choices.append(Choice("two-col", (1, 2, 3), lambda: cols([(None, f"<p>{e(value)}</p>") for value in points])))
    if n == 3 and fits(points, 140):
        choices.append(Choice("three-col", (1, 2, 3), lambda: cols([(None, f"<p>{e(value)}</p>") for value in points])))
    if n == 4 and fits(points, 90):
        choices.append(Choice("four-col", VARIANTS, lambda: cols([(None, f"<p>{e(value)}</p>") for value in points])))
    pairs = pairs_of(points, 26)
    if pairs and 3 <= n <= 5 and fits([h for h, _ in pairs], 22) and fits([x for _, x in pairs], 64):
        choices.append(Choice("text-boxes", VARIANTS, lambda: boxes(pairs)))
    if pairs and 3 <= n <= 4 and fits([x for _, x in pairs], 90):
        choices.append(Choice("icons", VARIANTS, lambda: icons(pairs)))
    if 4 <= n <= 8 and fits(points, 60):
        choices.append(Choice("small-icons", VARIANTS, lambda: small_icons(points)))
    if 2 <= n <= 4 and len(heading) <= 40 * ROOM and fits(points[:1], 56) and fits(points[1:], 56):
        choices.append(Choice("accent", VARIANTS, lambda: accent(t("Key point", "Ý chính"), points[0], points[1:])))
    return dedupe(choices)


def step_choices(points, t):
    n, choices = len(points), []
    numbered = lambda: items(points, "bullets", "ol")
    choices.append(Choice("bullets", (1, 3, 4) if fits(points, 64) else (1, 3), numbered))
    pairs = pairs_of(points, 32)
    label = lambda k: t(f"Step {k + 1}", f"Bước {k + 1}")
    # Steps rarely have titles; then the step number heads each one and the step itself is the text.
    rows = pairs or [(label(k), value) for k, value in enumerate(points)]
    heads, texts = [h for h, _ in rows], [x for _, x in rows]
    if 3 <= n <= 5:
        # Arrows and boxes number their items themselves, so a "Step 1" heading would repeat the ordinal:
        # they take steps that have titles, or steps short enough to be the heading.
        if not pairs and fits(points, 18):
            choices.append(Choice("arrows", VARIANTS, lambda: arrows([(value, None) for value in points])))
        elif pairs and fits(heads, 18) and fits(texts, 60):
            choices.append(Choice("arrows", VARIANTS, lambda: arrows(rows)))
        if fits(heads, 24) and fits(texts, 64):
            choices.append(Choice("timeline", (1, 2, 3), lambda: timeline(
                [(label(k), h, x) for k, (h, x) in enumerate(pairs)] if pairs else [(label(k), None, value) for k, value in enumerate(points)])))
        if fits(heads, 32) and fits(texts, 50):
            choices.append(Choice("timeline-v", (1, 2, 3), lambda: timeline(
                [(label(k), h, x) for k, (h, x) in enumerate(pairs)] if pairs else [(label(k), None, value) for k, value in enumerate(points)])))
        if pairs and fits(heads, 22) and fits(texts, 64):
            choices.append(Choice("text-boxes", VARIANTS, lambda: boxes(rows)))
    if 2 <= n <= 4 and fits(points, 56):
        choices.append(Choice("big-bullets", (1, 2, 3), lambda: items(points, "big-list", "ol")))
    return dedupe(choices)


def entry_bullets(entries):
    # One span per row: bullet rows are a grid of ordinal and text, so label and text must stay one cell.
    return items([f"<span><strong>{e(entry.label)}</strong> {e(entry.text)}</span>" for entry in entries], "bullets", raw=True)


def timeline_choices(entries, t):
    n, labels, texts = len(entries), [x.label for x in entries], [x.text for x in entries]
    choices = []
    if 3 <= n <= 5:
        if fits(labels, 9):
            choices.append(Choice("timeline", (1, 2, 3), lambda: timeline(
                [(x.label, x.text if len(x.text) <= 24 * ROOM else None, None if len(x.text) <= 24 * ROOM else x.text) for x in entries])))
        if fits(labels, 12):
            choices.append(Choice("timeline-v", (1, 2, 3), lambda: timeline(
                [(x.label, x.text if len(x.text) <= 32 * ROOM else None, None if len(x.text) <= 32 * ROOM else x.text) for x in entries])))
        if fits(labels, 18) and fits(texts, 60):
            choices.append(Choice("arrows", VARIANTS, lambda: arrows([(x.label, x.text) for x in entries])))
    if n == 2:
        choices.append(Choice("two-col-head", VARIANTS, lambda: cols([(x.label, f"<p>{e(x.text)}</p>") for x in entries])))
    if not choices:  # labelled rows only when no timeline form fits
        choices.append(Choice("bullets", (1, 3), lambda: entry_bullets(entries)))
    return dedupe(choices)


def column_choices(layout, columns):
    heads, n = [c.heading for c in columns], len(columns)
    blocks = lambda: cols([(c.heading, plain(c.points)) for c in columns])
    if layout == "compare" or n == 2:
        return [Choice("two-col-head", VARIANTS, blocks)]
    choices = []
    if n == 3:
        choices.append(Choice("three-col-head", (1, 2, 4), blocks))
    if n == 4:
        choices.append(Choice("four-col", VARIANTS, blocks))
    single = all(len(c.points) == 1 for c in columns)
    if single and 3 <= n <= 4 and fits(heads, 22) and fits([c.points[0] for c in columns], 64):
        choices.append(Choice("text-boxes", VARIANTS, lambda: boxes([(c.heading, c.points[0]) for c in columns])))
    return choices


def table_choices(columns):
    rows = list(zip(*[c.points for c in columns]))

    def table():
        head = "".join(f"<th>{e(c.heading)}</th>" for c in columns)
        body = "".join(f"<tr{part(k)}><th scope=\"row\">{e(row[0])}</th>" + "".join(f"<td>{e(cell)}</td>" for cell in row[1:]) + "</tr>"
                       for k, row in enumerate(rows))
        return f'<table class="data-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'
    # Key-row and key-column variants need a key the content does not mark, so they are left out.
    choices = [Choice("table", (1, 3, 4), table)]
    if len(rows) == 3:
        choices.append(Choice("table-3row", (1, 2, 4), table))
    return choices


def level_choices(layout, entries):
    rows = [(x.label, x.text) for x in entries]
    labels, notes = [x.label for x in entries], [x.text for x in entries]
    choices = []
    if layout == "funnel":
        if fits(labels, 18):
            allowed = tuple(v for v, limit in ((1, 60), (2, 45), (3, 50)) if fits(notes, limit))
            if allowed:
                choices.append(Choice("funnel", allowed, lambda: levels(rows)))
    else:
        if fits(labels, 20) and fits(notes, 50):
            choices.append(Choice("pyramid", ((1,) if fits(notes, 36) else ()) + (2, 3, 4), lambda: levels(rows)))
        if fits(labels, 24) and fits(notes, 50):
            choices.append(Choice("pyramid-outline", VARIANTS, lambda: levels(rows)))
        if fits(labels, 26) and fits(notes, 50):
            choices.append(Choice("pyramid-left", ((1,) if fits(labels, 18) else ()) + (2, 3, 4), lambda: levels(rows)))
    if not choices and layout == "funnel" and fits(labels, 18) and fits(notes, 60):
        choices.append(Choice("arrows", VARIANTS, lambda: arrows(rows)))  # stages too long for the bands still run in order
    if not choices:
        choices.append(Choice("bullets", (1, 3), lambda: entry_bullets(entries)))
    return choices


def stat_choices(entries):
    n, figures = len(entries), [figure(x.label) for x in entries]
    notes = [x.text for x in entries]
    choices = []
    if all(figures) and all(len(value) <= (4 if n == 4 else 5) and len(unit) <= 4 * ROOM for value, unit in figures):
        allowed = tuple(v for v, limit in ((1, 80), (2, 60), (3, 70), (4, 60)) if fits(notes, limit))
        if allowed:
            choices.append(Choice("big-numbers", allowed, lambda: '<ul class="kpis">' + "".join(
                f'<li class="kpi"{part(k)}><p class="kpi-value">{e(value)}<span class="unit">{e(unit)}</span></p><p class="kpi-note">{e(note)}</p></li>'
                for k, ((value, unit), note) in enumerate(zip(figures, notes))) + "</ul>"))
    values = [number(value) for value, _ in figures] if all(figures) else []
    single = values and all(v is not None for v in values)
    if single and all(unit == "%" for _, unit in figures) and all(0 <= v <= 100 for v in values) and fits(notes, 50):
        choices.append(Choice("circle-stats", VARIANTS, lambda: '<ul class="rings">' + "".join(
            f'<li style="--p:{value:g}"{part(k)}><span class="ring-value">{e(x.label)}</span>'
            + (f'<span class="ring-label">{e(x.text)}</span>' if len(x.text) <= 20 * ROOM else f'<span class="ring-note">{e(x.text)}</span>') + "</li>"
            for k, (value, x) in enumerate(zip(values, entries))) + "</ul>"))
    if single and n >= 3 and len({unit for _, unit in figures}) == 1 and min(values) >= 0 and fits(notes, 32):
        top = 100 if figures[0][1] == "%" else max(values)
        choices.append(Choice("bar-stats", (1, 2, 4), lambda: f'<ul class="bars" style="--max:{top:g}">' + "".join(
            f'<li style="--v:{value:g}"{part(k)}><span class="bar-label">{e(x.text)}</span><span class="bar-value">{e(x.label)}</span></li>'
            for k, (value, x) in enumerate(zip(values, entries))) + "</ul>"))
    if not choices:
        if n >= 3 and fits([x.label for x in entries], 22) and fits(notes, 64):
            choices.append(Choice("text-boxes", VARIANTS, lambda: boxes([(x.label, x.text) for x in entries])))
        elif n == 2:
            choices.append(Choice("two-col-head", VARIANTS, lambda: cols([(x.label, f"<p>{e(x.text)}</p>") for x in entries])))
        else:
            choices.append(Choice("bullets", (1, 3), lambda: entry_bullets(entries)))
    return choices


def dedupe(choices):
    seen, kept = set(), []
    for choice in choices:
        if choice.layout not in seen:
            seen.add(choice.layout)
            kept.append(choice)
    return kept


def next_variant(allowed, after):
    """The first allowed variant after `after` in the cycle 1, 2, 3, 4, 1."""
    return min(allowed, key=lambda variant: (variant - after - 1) % len(VARIANTS))


def arrange(slides, start):
    """Choose each slide's layout and variant.

    Layouts rotate within a kind (the n-th points slide starts its search at the n-th choice); a layout is not
    used three slides running and not twice in a row when another fits; variants cycle per layout; two full-surface
    fills never touch; accent panels move round left, right, top and the fit forms. Deterministic for a deck."""
    turns, last, history, accents = {}, {}, [], 0
    for slide in slides:
        choices = slide.get("choices")
        if not choices:
            history.append((slide["kind"], 0))
            continue
        turn = turns[slide["kind"]] = turns.get(slide["kind"], -1) + 1
        offset = (start + turn) % len(choices)
        ordered = choices[offset:] + choices[:offset]
        previous = history[-1] if history else (None, 0)
        before = history[-2] if len(history) > 1 else (None, 0)
        concrete = lambda choice: ACCENTS[accents % len(ACCENTS)] if choice.layout == "accent" else choice.layout
        fresh = [c for c in ordered if concrete(c) != previous[0]]
        if not fresh and previous[0] == before[0]:
            fresh = ordered[1:] or ordered
        choice = (fresh or ordered)[0]
        layout = concrete(choice)
        if choice.layout == "accent":
            accents += 1
        variants = choice.variants
        variant = next_variant(variants, last.get(layout, start % len(VARIANTS)))
        if (layout, variant) == previous or ((layout, variant) in HEAVY and previous in HEAVY):
            others = [v for v in variants if (layout, v) != previous and (layout, v) not in HEAVY]
            if others:
                variant = next_variant(others, variant)
        last[layout] = variant
        history.append((layout, variant))
        slide.update(layout=layout, variant=variant, content=choice.build())
        if choice.heading is not None:
            slide["heading"] = choice.heading
    return slides
