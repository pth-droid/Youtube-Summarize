"""Structure edits for lecture decks: hide, show, delete, duplicate, move and add slides, change a slide's layout, undo and redo.

Decks are records, not free canvases: a plan is parts, a part holds one to six slides, and a slide is addressed by its part
and its place in the part, both counted from 0 (the deck marks them data-slide="P.S"). A structure edit changes the saved
plan in lecture.json and draws the deck again, like a text save (deck_edits), and the grounding rules still hold: every slide
keeps the ideas it teaches, and the deck is checked with validate_lecture before anything is written. Text changes that were
not saved yet travel with the edit, so one request is one atomic step. No AI request is made.
"""
from __future__ import annotations

import copy

from pydantic import ValidationError

from . import deck_convert
from .deck_edits import HISTORY_STEPS, EditError, apply, load_history, problem, records_version, snapshot, write_deck
from .models import KnowledgeModel, LecturePlan
from .share import deck_look, deck_records

PART_SLIDES = 6
OPS = ("hide", "show", "delete", "duplicate", "move", "add", "layout", "undo", "redo")
LABELS = {"hide": "Hide slide", "show": "Show slide", "delete": "Delete slide", "duplicate": "Duplicate slide", "move": "Move slide",
          "add": "Add slide", "layout": "Change layout"}


def gone() -> EditError:
    return EditError("This slide is no longer in the deck. Reload the editor.", 409)


def locate(parts: list[dict], at) -> tuple[int, int]:
    """A slide's part and place, checked against the plan."""
    try:
        part, place = int(at[0]), int(at[1])
        if part < 0 or place < 0:
            raise IndexError
        parts[part]["slides"][place]
    except (TypeError, IndexError, ValueError, KeyError) as error:
        raise gone() from error
    return part, place


def new_slide(neighbour: dict, vi: bool) -> dict:
    """A blank points slide that teaches the same ideas as the slide beside it, so it stays tied to the source."""
    return {"layout": "points", "title": "Slide mới" if vi else "New slide", "points": ["Nhập ý của bạn ở đây." if vi else "Type your point here."],
            "columns": [], "entries": [], "unit_ids": list(neighbour["unit_ids"]), "notes": "", "hidden": False}


def change(lecture: dict, knowledge: KnowledgeModel, op: dict) -> tuple[str | None, list[str]]:
    """Apply one structure edit to the plan's records. Returns where the edited slide is now ("P.S"), and warnings."""
    parts, kind, warnings = lecture["parts"], op["type"], []
    if kind == "add":
        part = locate(parts, (op.get("part"), 0))[0]
        slides = parts[part]["slides"]
        if len(slides) >= PART_SLIDES:
            raise EditError(f"A part holds at most {PART_SLIDES} slides. Delete or move one first.")
        place = len(slides) if op.get("index") is None else int(op["index"])
        if not 0 <= place <= len(slides):
            raise gone()
        slides.insert(place, new_slide(slides[max(place - 1, 0)], knowledge.language == "vi"))
        return f"{part}.{place}", warnings
    part, place = locate(parts, op.get("slide"))
    slides = parts[part]["slides"]
    slide = slides[place]
    if kind in ("hide", "show"):
        slide["hidden"] = kind == "hide"
        return f"{part}.{place}", warnings
    if kind == "delete":
        if len(slides) == 1:
            raise EditError("A part keeps at least one slide. Add another first, or hide this one.")
        slides.pop(place)
        return f"{part}.{max(place - 1, 0)}", warnings
    if kind == "duplicate":
        if len(slides) >= PART_SLIDES:
            raise EditError(f"A part holds at most {PART_SLIDES} slides. Delete or move one first.")
        slides.insert(place + 1, copy.deepcopy(slide))
        return f"{part}.{place + 1}", warnings
    if kind == "move":
        target = op.get("to")
        try:
            to_part, to_place = int(target[0]), int(target[1])
            destination = parts[to_part]["slides"]
        except (TypeError, IndexError, ValueError) as error:
            raise EditError("That place is not in the deck.", 409) from error
        if to_part != part and len(slides) == 1:
            raise EditError("A part keeps at least one slide. Add another first, or hide this one.")
        if to_part != part and len(destination) >= PART_SLIDES:
            raise EditError(f"A part holds at most {PART_SLIDES} slides. Delete or move one first.")
        slides.pop(place)
        if not 0 <= to_place <= len(destination):
            raise EditError("That place is not in the deck.", 409)
        destination.insert(to_place, slide)
        return f"{to_part}.{to_place}", warnings
    if kind == "layout":
        try:
            parts[part]["slides"][place], warnings = deck_convert.convert(knowledge, slide, str(op.get("layout")))
        except deck_convert.Unavailable as error:
            raise EditError(str(error)) from error
        return f"{part}.{place}", warnings
    raise EditError("This edit is not known.")


def restored(folder_records: tuple, step: dict) -> tuple[KnowledgeModel, LecturePlan]:
    """The records an edit step saved, with the part titles it saved."""
    knowledge, lecture = folder_records
    try:
        plan = LecturePlan.model_validate(step["lecture"])
        model = knowledge.model_copy(deep=True)
        for chapter in model.chapters:
            chapter.title = step["chapters"].get(chapter.id, chapter.title)
        return KnowledgeModel.model_validate(model.model_dump(mode="json")), plan
    except (ValidationError, KeyError, TypeError, AttributeError) as error:
        raise EditError("This step can no longer be restored.", 409) from error


def structure(store, generation: dict, version: str, changes: list[dict], op: dict) -> dict:
    """Make one structure edit, with the text changes that were not saved yet, and draw the deck again.

    Returns the deck's new version, the place of the edited slide (None after undo and redo), the warnings, and the steps
    that can be undone and redone. The saved records change only when the whole step is valid."""
    deck = store.managed_path(generation["page_path"])
    folder = deck.parent
    if version != records_version(folder):
        raise EditError("These slides changed in another window. Reload the editor.", 409)
    _, knowledge, lecture, _ = deck_records(folder)
    history = load_history(folder)
    undo, redo = list(history["undo"]), list(history["redo"])
    where, warnings = None, []
    if op["type"] in ("undo", "redo"):
        stack, other = (undo, redo) if op["type"] == "undo" else (redo, undo)
        if not stack:
            raise EditError(f"There is nothing to {op['type']}.", 409)
        step = stack.pop()
        other.append(snapshot(lecture, knowledge, step["label"]))
        model, edited = restored((knowledge, lecture), step)
        titles = {c.id: c.title for c in model.chapters} != {c.id: c.title for c in knowledge.chapters}
    else:
        records = {"lecture": lecture.model_dump(mode="json"), "knowledge": knowledge.model_dump(mode="json")}
        if changes:
            apply(records, changes)
        where, warnings = change(records["lecture"], knowledge, op)
        try:
            edited, model = LecturePlan.model_validate(records["lecture"]), KnowledgeModel.model_validate(records["knowledge"])
        except ValidationError as error:
            raise EditError(problem(error)) from error
        if edited.title != lecture.title and not edited.layout_seed:
            edited.layout_seed = lecture.title
        undo.append(snapshot(lecture, knowledge, LABELS[op["type"]]))
        redo = []
        titles = bool(changes) and any(edit["field"].startswith("chapters.") for edit in changes)
    write_deck(store, generation, folder, (model, edited), (undo, redo), titles=titles)
    return {"version": records_version(folder), "at": where, "warnings": warnings,
            "history": {"undo": min(len(undo), HISTORY_STEPS), "redo": min(len(redo), HISTORY_STEPS)}}


def slide_at(store, generation: dict, at: str):
    """The deck's records and the slide the editor named, for layout options and previews."""
    folder = store.managed_path(generation["page_path"]).parent
    source, knowledge, lecture, figures = deck_records(folder)
    try:
        part, place = (int(piece) for piece in at.split("."))
    except ValueError as error:
        raise gone() from error
    parts = lecture.model_dump(mode="json")["parts"]
    locate(parts, (part, place))
    return (source, knowledge, lecture, figures), (part, place), parts[part]["slides"][place]


def layout_options(store, generation: dict, at: str) -> list[dict]:
    (_, knowledge, _, _), _, slide = slide_at(store, generation, at)
    return deck_convert.options(knowledge, slide)


def layout_preview(store, generation: dict, at: str, layout: str) -> str:
    """The slide as it would look in another layout: the deck's page with only that slide in view, in the deck's look."""
    from .renderer import lecture_page
    from .slide_export import only_slide
    (source, knowledge, lecture, figures), (part, place), slide = slide_at(store, generation, at)
    try:
        slide, _ = deck_convert.convert(knowledge, slide, layout)
    except deck_convert.Unavailable as error:
        raise EditError(str(error)) from error
    plan = lecture.model_copy(deep=True)
    plan.parts[part].slides[place] = type(plan.parts[part].slides[place]).model_validate({**slide, "hidden": False})
    deck = store.managed_path(generation["page_path"])
    return only_slide(lecture_page(source, knowledge, plan, figures, deck_look(generation, deck)), f"{part}.{place}")
