"""Change one slide's layout in a lecture plan without asking the AI again.

A slide's content takes one of three shapes (its content family): points (points, steps, quote), columns (compare, columns,
table) or entries (timeline, pyramid, funnel, stats). To change layout, the slide is read as blocks, each a heading and
its points, then written in the shape of the new layout. Counts that the new layout cannot hold are cut or merged, and
each cut is a warning the person sees before applying. The result is checked with the contracts the AI's slides meet
(LectureSlide and validate_lecture), so a layout whose content the source does not support is unavailable, with the reason.
"""
from __future__ import annotations

from pydantic import ValidationError

from .deck_layouts import labelled
from .models import ENTRY_LAYOUTS, KnowledgeModel, LecturePart, LecturePlan, LectureSlide, validate_lecture

LAYOUTS = {
    "points": "Bullet points", "steps": "Steps", "compare": "Compare two", "columns": "Columns", "table": "Table",
    "timeline": "Timeline", "pyramid": "Pyramid", "funnel": "Funnel", "stats": "Key figures", "quote": "Quote",
}
HINTS = {
    "points": "Key ideas as short rows.", "steps": "An ordered procedure.", "compare": "Two options side by side.",
    "columns": "Two to four parallel groups, each with a heading.", "table": "Groups read across, row by row.",
    "timeline": "Ordered moments with a label each.", "pyramid": "Three to five levels, narrow top to broad base.",
    "funnel": "Three to five stages that narrow.", "stats": "Figures the source states, each with what it means.",
    "quote": "The source's own words, with your points beneath.",
}
FAMILY = {"points": "points", "steps": "points", "quote": "points", "compare": "columns", "columns": "columns", "table": "columns",
          "timeline": "entries", "pyramid": "entries", "funnel": "entries", "stats": "entries"}
TEXT, LABEL, HEADING, PER_COLUMN, POINTS = 260, 40, 120, 5, 6

Block = tuple[str | None, list[str]]


class Unavailable(ValueError):
    """The slide cannot take this layout; the message says why, in words for the person editing."""


def blocks_of(slide: dict) -> list[Block]:
    """The slide's content as headings with points; a points slide has one headingless block per point."""
    family = FAMILY[slide["layout"]]
    if family == "points":
        return [(None, [point]) for point in slide["points"]]
    if family == "entries":
        return [(entry["label"], [entry["text"]]) for entry in slide["entries"]]
    return [(column["heading"], list(column["points"])) for column in slide["columns"]]


def shorten(text: str, limit: int, warnings: list[str], what: str) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    warnings.append(f"{what} was shortened to {limit} characters.")
    return text[:limit - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def as_points(blocks: list[Block], warnings: list[str]) -> list[str]:
    points = []
    for head, body in blocks:
        text = f"{head}: {'; '.join(body)}" if head else " ".join(body)
        points.append(shorten(text, TEXT, warnings, "A point"))
    if len(points) > POINTS:
        warnings.append(f"{plural(len(points) - POINTS, 'point')} left out: a slide holds {POINTS}.")
    return points[:POINTS]


def as_entries(blocks: list[Block], low: int, high: int, layout: str, warnings: list[str]) -> list[dict]:
    entries, numbered = [], False
    for index, (head, body) in enumerate(blocks, 1):
        text = " ".join(body)
        if head is None and (pair := labelled(text, LABEL)):
            head, text = str(pair[0]), str(pair[1])
        if head is None:
            head, numbered = str(index), True
        entries.append({"label": shorten(head, LABEL, warnings, "A label"), "text": shorten(text, TEXT, warnings, "A text")})
    if len(entries) < low:
        raise Unavailable(f"A {layout} slide needs at least {low} items; this slide has {len(entries)}.")
    if len(entries) > high:
        warnings.append(f"{plural(len(entries) - high, 'item')} left out: a {layout} slide holds {high}.")
    if numbered:
        warnings.append("Some labels are numbers, because those points have no 'Label: text' form. Edit them after applying.")
    return entries[:high]


def as_columns(blocks: list[Block], layout: str, warnings: list[str], vi: bool) -> list[dict]:
    low, high = (2, 2) if layout == "compare" else (2, 4)
    if len(blocks) < low:
        raise Unavailable(f"A {layout} slide needs at least two groups; this slide has {len(blocks)}.")
    columns, placeholder = [], False
    for index, (head, body) in enumerate(blocks, 1):
        if head is None and (pair := labelled(body[0], HEADING)):
            head, body = str(pair[0]), [str(pair[1])]
        if head is None:
            head, placeholder = f"Ý {index}" if vi else f"Point {index}", True
        columns.append({"heading": head, "points": list(body)})
    if len(columns) > high:
        merged = columns[high - 1:]
        warnings.append(f"{plural(len(merged), 'group')} merged into the last column, {merged[0]['heading']!r}: a {layout} slide holds {high}.")
        columns[high - 1:] = [{"heading": merged[0]["heading"], "points": [point for column in merged for point in column["points"]]}]
    for column in columns:
        if len(column["points"]) > PER_COLUMN:
            warnings.append(f"{plural(len(column['points']) - PER_COLUMN, 'point')} left out of {column['heading']!r}: a column holds {PER_COLUMN}.")
            column["points"] = column["points"][:PER_COLUMN]
        column["points"] = [shorten(point, TEXT, warnings, "A point") for point in column["points"]]
        column["heading"] = shorten(column["heading"], HEADING, warnings, "A heading")
    if placeholder:
        warnings.append("Some headings are placeholders, because those points have no 'Label: text' form. Edit them after applying.")
    if layout == "table":
        rows = min(len(column["points"]) for column in columns)
        if any(len(column["points"]) != rows for column in columns):
            warnings.append(f"Every column was cut to {plural(rows, 'row')}, the fewest any column has: a table reads across.")
            for column in columns:
                column["points"] = column["points"][:rows]
    elif layout == "columns" and sum(len(column["points"]) for column in columns) > 12:
        raise Unavailable("A columns slide holds at most twelve points in all.")
    return columns


def candidate(slide: dict, layout: str, vi: bool = False) -> tuple[dict, list[str]]:
    """The slide in another layout, with what the change cuts or merges. Raises Unavailable when it cannot be made."""
    if layout not in LAYOUTS:
        raise Unavailable("This layout does not exist.")
    warnings: list[str] = []
    blocks = blocks_of(slide)
    changed = {**slide, "layout": layout, "points": [], "columns": [], "entries": []}
    family = FAMILY[layout]
    if family == "points":
        changed["points"] = as_points(blocks, warnings)
        if not changed["points"]:
            raise Unavailable("This slide has no text to carry over.")
    elif family == "entries":
        changed["entries"] = as_entries(blocks, *ENTRY_LAYOUTS[layout], layout, warnings)
    else:
        changed["columns"] = as_columns(blocks, layout, warnings, vi)
    return changed, warnings


def problem(error: ValidationError | ValueError) -> str:
    message = str(error.errors()[0]["msg"]).removeprefix("Value error, ") if isinstance(error, ValidationError) else str(error)
    if message.startswith("A stats figure"):
        return "A stats slide shows only figures the source states, and these labels are not."
    if message.startswith("A quote slide"):
        return "A quote slide needs an idea with the source's original words; this slide's ideas have none."
    return message


def convert(knowledge: KnowledgeModel, slide: dict, layout: str) -> tuple[dict, list[str]]:
    """The checked slide in another layout, and its warnings; raises Unavailable with the reason when the source or the
    layout's limits do not allow it."""
    if layout == slide["layout"]:
        raise Unavailable("The slide already has this layout.")
    changed, warnings = candidate(slide, layout, knowledge.language == "vi")
    try:
        checked = LectureSlide.model_validate(changed)
        # The same check the saved deck passes: known ideas, a quote's evidence, and the figures a stats slide shows.
        validate_lecture(knowledge, LecturePlan(title="x", objectives=["x", "x"], takeaways=["x", "x"],
                                               parts=[LecturePart(chapter_id="overview", slides=[checked])]))
    except (ValidationError, ValueError) as error:
        raise Unavailable(problem(error)) from error
    return checked.model_dump(mode="json"), warnings


def options(knowledge: KnowledgeModel, slide: dict) -> list[dict]:
    """Every layout, with whether this slide can take it, why not, and what taking it would cut."""
    found = []
    for layout, name in LAYOUTS.items():
        entry = {"layout": layout, "name": name, "hint": HINTS[layout], "current": layout == slide["layout"], "available": False, "reason": "", "warnings": []}
        try:
            if not entry["current"]:
                entry["warnings"] = convert(knowledge, slide, layout)[1]
                entry["available"] = True
        except Unavailable as error:
            entry["reason"] = str(error)
        found.append(entry)
    return found
