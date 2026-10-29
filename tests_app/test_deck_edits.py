"""Edit mode for lecture decks: text marked in place, changes saved into the deck's records, and the deck drawn again."""
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from distill.app import create_app
from distill.deck_edits import EditError, apply, records_version, save_edits
from distill.models import LectureEntry, LecturePart, LecturePlan, LectureSlide
from distill.renderer import lecture_page, render_lecture
from distill.share import PHONE_PAGE
from tests_app.figure_fixture import figure_fixture
from tests_app.test_lecture import slide
from tests_app.test_share import made

LAYOUTS = re.compile(r'class="slide kind-[\w-]+(?: layout-[\w-]+ variant-\d)?')


def roast_plan():
    """Two parts, so the deck has an agenda and section slides; labelled steps with notes, and a stats slide."""
    stats = LectureSlide(layout="stats", title="Một shot", unit_ids=["shot", "control_chart"],
                         entries=[LectureEntry(label="36 g", text="Khối lượng"), LectureEntry(label="28 giây", text="Thời gian")])
    steps = slide("steps", ids=("charge",), title="Theo thứ tự", points=["Nạp: đổ hạt vào", "Sấy: hạt mất nước", "Nâu: Maillard"],
                  notes="Câu một.\nCâu hai.")
    return LecturePlan(title="Rang và chiết", objectives=["Giải thích nhiệt.", "So sánh rang."], takeaways=["Nhiệt quyết định.", "Đo lường."],
                       parts=[LecturePart(chapter_id="chapter_01", slides=[steps]), LecturePart(chapter_id="chapter_02", slides=[stats])])


def saved_deck(tmp_path):
    """A deck as a generation keeps it: the page, and the records it is drawn from beside it."""
    source, knowledge, _ = figure_fixture()
    folder = tmp_path / "deck"
    folder.mkdir()
    lecture = roast_plan()
    for name, record in (("source", source), ("knowledge", knowledge), ("lecture", lecture)):
        (folder / f"{name}.json").write_text(record.model_dump_json(indent=2), encoding="utf-8")
    render_lecture(source, knowledge, lecture, folder / "lecture.html", theme="maroon")
    store = SimpleNamespace(managed_path=Path, custom_looks=dict)
    return store, {"page_path": str(folder / "lecture.html"), "metadata": {"slide_theme": "maroon"}}, folder


def test_edit_mode_marks_each_text_in_place_and_draws_the_same_slides():
    source, knowledge, _ = figure_fixture()
    shown = lecture_page(source, knowledge, roast_plan(), theme="maroon")
    editing = lecture_page(source, knowledge, roast_plan(), theme="maroon", editable=True)
    # The deck itself carries no edit marks or edit script; the edit page chooses the same layouts for the same slides.
    assert "data-field" not in shown and "distill-edit" not in shown and "distill-edit" in editing
    assert LAYOUTS.findall(shown) == LAYOUTS.findall(editing)
    assert '<span data-field="title" data-limit="160">Rang và chiết</span>' in editing
    # A figure is shown as its value and unit; each piece keeps its place in the label.
    assert '<span data-field="parts.1.slides.0.entries.0.label" data-span="0:2">36</span>' in editing
    assert '<span data-field="parts.1.slides.0.entries.0.label" data-span="3:4">g</span>' in editing
    # Part titles live in the knowledge model; they can be edited on the agenda and on their section slides.
    assert editing.count('data-field="chapters.0.title"') >= 2
    # Notes are one text that keeps its paragraphs; a slide without notes has an empty one to type into.
    assert re.search(r'<div class="notes-text" data-field="parts\.0\.slides\.0\.notes" data-limit="1600" data-lines [^>]*>'
                     r'<p>Câu một\.</p><p>Câu hai\.</p></div>', editing)
    assert re.search(r'data-field="parts\.1\.slides\.0\.notes"[^>]*></div>', editing)


def test_pieces_of_a_text_go_back_into_it_from_the_end():
    records = {"lecture": {"parts": [{"slides": [{"points": ["Nạp: đổ hạt vào"]}]}]}, "knowledge": {}}
    apply(records, [{"field": "parts.0.slides.0.points.0", "span": "0:3", "text": "Charge"},
                    {"field": "parts.0.slides.0.points.0", "span": "5:15", "text": "beans in"}])
    assert records["lecture"]["parts"][0]["slides"][0]["points"][0] == "Charge: beans in"
    with pytest.raises(EditError, match="changed since"):  # pieces never overlap
        apply(records, [{"field": "parts.0.slides.0.points.0", "span": "0:5", "text": "a"},
                        {"field": "parts.0.slides.0.points.0", "span": "3:8", "text": "b"}])


def test_a_save_puts_the_changes_into_the_records_and_draws_the_deck_again(tmp_path):
    store, generation, folder = saved_deck(tmp_path)
    version = records_version(folder)
    save_edits(store, generation, version, [
        {"field": "parts.0.slides.0.title", "span": "", "text": "  Ba   bước  "},
        {"field": "parts.1.slides.0.entries.1.label", "span": "3:7", "text": "s"},
        {"field": "parts.0.slides.0.notes", "span": "", "text": "Mở đầu.\n\n  Kết thúc. "},
        {"field": "chapters.1.title", "span": "", "text": "Pha espresso"}])
    lecture = json.loads((folder / "lecture.json").read_text(encoding="utf-8"))
    steps = lecture["parts"][0]["slides"][0]
    assert steps["title"] == "Ba bước" and steps["notes"] == "Mở đầu.\nKết thúc."
    assert lecture["parts"][1]["slides"][0]["entries"][1]["label"] == "28 s"
    assert json.loads((folder / "knowledge.json").read_text(encoding="utf-8"))["chapters"][1]["title"] == "Pha espresso"
    page = (folder / "lecture.html").read_text(encoding="utf-8")
    assert "Ba bước" in page and "Pha espresso" in page and "data-field" not in page
    # The page those edits were made on is out of date now, so nothing more from it can land.
    with pytest.raises(EditError, match="changed in another window") as refused:
        save_edits(store, generation, version, [{"field": "title", "span": "", "text": "Khác"}])
    assert refused.value.status == 409


def test_a_renamed_deck_keeps_its_layouts_and_a_shared_phone_copy_follows_the_edit(tmp_path):
    store, generation, folder = saved_deck(tmp_path)
    before = LAYOUTS.findall((folder / "lecture.html").read_text(encoding="utf-8"))
    (folder / PHONE_PAGE).write_text("the phone copy shared before", encoding="utf-8")
    save_edits(store, generation, records_version(folder), [{"field": "title", "span": "", "text": "Một tên khác hẳn"}])
    lecture = json.loads((folder / "lecture.json").read_text(encoding="utf-8"))
    assert lecture["title"] == "Một tên khác hẳn" and lecture["layout_seed"] == "Rang và chiết"
    assert LAYOUTS.findall((folder / "lecture.html").read_text(encoding="utf-8")) == before
    phone = (folder / PHONE_PAGE).read_text(encoding="utf-8")
    assert "Một tên khác hẳn" in phone and 'data-mode="phone"' in phone


def test_edits_that_would_break_the_slides_are_refused_and_change_nothing(tmp_path):
    store, generation, folder = saved_deck(tmp_path)
    records = [(folder / name).read_bytes() for name in ("lecture.json", "knowledge.json", "lecture.html")]
    for change, message in (
            ({"field": "parts.0.slides.0.points.0", "span": "", "text": "   "}, "is empty"),
            ({"field": "parts.0.slides.0.title", "span": "", "text": "x" * 141}, "at most 140 characters"),
            ({"field": "parts.1.slides.0.entries.0.label", "span": "0:2", "text": "40"}, "number its cited ideas state"),
            ({"field": "parts.0.slides.0.unit_ids.0", "span": "", "text": "maillard"}, "cannot be edited"),
            ({"field": "parts.0.slides.9.title", "span": "", "text": "Gone"}, "no longer in the slides"),
            ({"field": "title", "span": "40:41", "text": "x"}, "changed since")):
        with pytest.raises(EditError, match=message):
            save_edits(store, generation, records_version(folder), [change])
    assert [(folder / name).read_bytes() for name in ("lecture.json", "knowledge.json", "lecture.html")] == records


def test_the_reader_edits_a_deck_through_its_routes(tmp_path):
    app = create_app(tmp_path)
    store = app.state.store
    deck, page = made(store, "lecture"), made(store, "page")
    with TestClient(app, base_url="http://127.0.0.1") as client:
        headers = {"x-distill": app.state.csrf_token}
        editing = client.get(f"/api/generations/{deck}/slides/edit")
        # The edit page runs sandboxed like the deck, in the deck's look, and names the records it was drawn from.
        assert editing.status_code == 200 and editing.headers["content-security-policy"].startswith("sandbox allow-scripts")
        assert 'data-field="parts.0.slides.0.points.1"' in editing.text and '<style id="look">' in editing.text
        version = re.search(r'<meta name="distill-version" content="([0-9a-f]{16})">', editing.text)[1]
        assert client.get(f"/api/generations/{page}/slides/edit").status_code == 409
        body = {"version": version, "changes": [{"field": "parts.0.slides.0.points.1", "text": "A second, different idea."}]}
        assert client.put(f"/api/generations/{deck}/slides", json=body).status_code == 403
        assert client.put(f"/api/generations/{page}/slides", json=body, headers=headers).status_code == 409
        assert client.put(f"/api/generations/{deck}/slides", json=body, headers=headers).json() == {"saved": 1}
        shown = client.get(f"/api/generations/{deck}/page").text
        assert "A second, different idea." in shown and "data-field" not in shown
        assert "A second, different idea." in client.get(f"/api/generations/{deck}/export").text
        refused = client.put(f"/api/generations/{deck}/slides", json=body, headers=headers)
        assert refused.status_code == 409 and "another window" in refused.json()["detail"]
        version = re.search(r'name="distill-version" content="(\w+)"', client.get(f"/api/generations/{deck}/slides/edit").text)[1]
        empty = client.put(f"/api/generations/{deck}/slides", headers=headers,
                           json={"version": version, "changes": [{"field": "title", "text": " "}]})
        assert empty.status_code == 422 and "is empty" in empty.json()["detail"]
