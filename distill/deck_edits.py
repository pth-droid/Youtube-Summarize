"""Edit mode for lecture decks: a person changes slide text in place, and the deck is drawn again from its records.

The edit page is the deck rendered from its saved records with each text a person may change marked by its place in
them (renderer.editable_plan). A save puts the changes into lecture.json, and part titles into knowledge.json, checks
them with the contracts the AI's slides meet, and renders the deck, and its phone copy if it was shared, again.
No AI request is made.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from pydantic import ValidationError

from .looks import with_custom_look
from .models import KnowledgeModel, LecturePlan, validate_lecture
from .pipeline import write_json
from .renderer import lecture_page, write_page
from .share import deck_look, deck_records, phone_page, render_phone

# Every place a text can be edited: the deck title, objectives and takeaways, the text of each slide, and part titles.
FIELD = re.compile(r"title|(?:objectives|takeaways)\.\d+|chapters\.\d+\.title|parts\.\d+\.slides\.\d+\."
                   r"(?:title|notes|points\.\d+|columns\.\d+\.(?:heading|points\.\d+)|entries\.\d+\.(?:label|text))")
SPAN = re.compile(r"(\d+):(\d+)")


class EditError(ValueError):
    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


def records_version(folder: Path) -> str:
    """Names the saved text an edit page was drawn from, so a save never lands on text that changed since."""
    digest = hashlib.sha256()
    for name in ("lecture.json", "knowledge.json"):
        digest.update((folder / name).read_bytes())
    return digest.hexdigest()[:16]


def edit_page(store, generation: dict) -> str:
    """The deck in edit mode, in its look with the look's saved changes, as the reader shows it."""
    deck = store.managed_path(generation["page_path"])
    source, knowledge, lecture, figures = deck_records(deck.parent)
    page = lecture_page(source, knowledge, lecture, figures, deck_look(generation, deck), editable=True)
    page = page.replace("</head>", f'<meta name="distill-version" content="{records_version(deck.parent)}"></head>', 1)
    return with_custom_look(page, store.custom_looks())


def clean(text: str, field: str) -> str:
    """Notes keep their paragraphs; every other text is one line."""
    if field.endswith(".notes"):
        return "\n".join(" ".join(line.split()) for line in text.splitlines() if line.strip())
    return " ".join(text.split())


def apply(records: dict, changes: list[dict]) -> None:
    """Put each change into the records. A change to a piece of a text, such as the label of 'Label: text', replaces
    that piece's character span; spans go in from the end of the text, so the earlier ones keep their place."""
    by_field = {}
    for change in changes:
        if not FIELD.fullmatch(change["field"]):
            raise EditError("This text cannot be edited.")
        by_field.setdefault(change["field"], []).append(change)
    for field, edits in by_field.items():
        keys = [int(key) if key.isdigit() else key for key in field.split(".")]
        container = records["knowledge"] if keys[0] == "chapters" else records["lecture"]
        try:
            for key in keys[:-1]:
                container = container[key]
            value = container[keys[-1]]
        except (KeyError, IndexError, TypeError) as error:
            raise EditError("This text is no longer in the slides. Cancel, then edit again.", 409) from error
        whole = [edit for edit in edits if not edit["span"]]
        if whole:
            value = whole[-1]["text"]
        else:
            end_of_next = len(value)
            for edit in sorted(edits, key=lambda edit: int(SPAN.fullmatch(edit["span"])[1]), reverse=True):
                start, end = map(int, SPAN.fullmatch(edit["span"]).groups())
                if not start <= end <= end_of_next:
                    raise EditError("This text changed since the slides were opened. Cancel, then edit again.", 409)
                value, end_of_next = value[:start] + edit["text"] + value[end:], start
        container[keys[-1]] = clean(value, field)


def problem(error: ValidationError) -> str:
    first = error.errors()[0]
    if first["type"] == "string_too_short":
        return "A slide text is empty. Type it again, or press Esc in it to put the old text back."
    if first["type"] == "string_too_long":
        return f"A slide text is too long: its place holds at most {first['ctx']['max_length']} characters."
    return "These changes cannot be saved. Cancel, then edit again."


def save_edits(store, generation: dict, version: str, changes: list[dict]) -> None:
    deck = store.managed_path(generation["page_path"])
    folder = deck.parent
    if version != records_version(folder):
        raise EditError("These slides changed in another window. Cancel, then edit them again.", 409)
    source, knowledge, lecture, figures = deck_records(folder)
    records = {"lecture": lecture.model_dump(mode="json"), "knowledge": knowledge.model_dump(mode="json")}
    apply(records, changes)
    try:
        edited, model = LecturePlan.model_validate(records["lecture"]), KnowledgeModel.model_validate(records["knowledge"])
    except ValidationError as error:
        raise EditError(problem(error)) from error
    if edited.title != lecture.title and not edited.layout_seed:
        edited.layout_seed = lecture.title  # a renamed deck keeps the layouts its first title chose
    try:
        validate_lecture(model, edited)
    except ValueError as error:  # a figure on a stats slide that the source does not state
        raise EditError(f"{error}. Put the figure the source states back.") from error
    page = lecture_page(source, model, edited, figures, deck_look(generation, deck))
    if any(change["field"].startswith("chapters.") for change in changes):
        write_json(folder / "knowledge.json", model.model_dump(mode="json"))
    write_json(folder / "lecture.json", edited.model_dump(mode="json"))
    write_page(deck, page)
    if phone_page(store, generation).is_file():
        render_phone(store, generation)
