"""Structure edits for lecture decks: hide, show, delete, duplicate, move, add, change layout, undo and redo."""
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from distill import deck_convert
from distill.app import create_app
from distill.deck_edits import HISTORY, EditError, edit_page, load_history, records_version
from distill.deck_structure import structure
from distill.models import LectureColumn, LectureEntry, LectureParts, LecturePart, LecturePlan, LectureSlide
from distill.renderer import lecture_page, render_lecture
from distill.share import PHONE_PAGE
from tests_app.figure_fixture import figure_fixture
from tests_app.test_deck_edits import LAYOUTS
from tests_app.test_share import made


def slide(layout="points", title="A slide", ids=("charge",), **content):
    shapes = {"points": {"points": ["Nạp: đổ hạt vào", "Sấy: hạt mất nước", "Nâu: Maillard"]},
              "steps": {"points": ["Một bước", "Hai bước", "Ba bước"]}}
    return LectureSlide(layout=layout, title=title, unit_ids=list(ids), **(shapes.get(layout, {}) | content))


def plan():
    """Part 0 holds three slides, part 1 a stats slide and a points slide; the fixture's source is Vietnamese."""
    stats = LectureSlide(layout="stats", title="Một shot", unit_ids=["shot", "control_chart"],
                         entries=[LectureEntry(label="36 g", text="Khối lượng"), LectureEntry(label="28 giây", text="Thời gian")])
    compare = LectureSlide(layout="compare", title="So sánh", unit_ids=["heat"], columns=[
        LectureColumn(heading="Dẫn nhiệt", points=["Qua trống"]), LectureColumn(heading="Đối lưu", points=["Qua khí"])])
    return LecturePlan(title="Rang và chiết", objectives=["Giải thích nhiệt.", "So sánh rang."], takeaways=["Nhiệt quyết định.", "Đo lường."],
                       parts=[LecturePart(chapter_id="chapter_01", slides=[slide(title="Một"), slide("steps", "Hai", ("drying",)), compare]),
                              LecturePart(chapter_id="chapter_02", slides=[stats, slide(title="Năm", ids=("pressure",))])])


def saved_deck(tmp_path):
    source, knowledge, _ = figure_fixture()
    folder = tmp_path / "deck"
    folder.mkdir()
    lecture = plan()
    for name, record in (("source", source), ("knowledge", knowledge), ("lecture", lecture)):
        (folder / f"{name}.json").write_text(record.model_dump_json(indent=2), encoding="utf-8")
    render_lecture(source, knowledge, lecture, folder / "lecture.html", theme="maroon")
    store = SimpleNamespace(managed_path=Path, custom_looks=dict)
    return store, {"page_path": str(folder / "lecture.html"), "metadata": {"slide_theme": "maroon"}}, folder


def op(store, generation, folder, kind, changes=(), **values):
    return structure(store, generation, records_version(folder), list(changes), {"type": kind, **values})


def titles(folder):
    saved = json.loads((folder / "lecture.json").read_text(encoding="utf-8"))
    return [[slide["title"] for slide in part["slides"]] for part in saved["parts"]]


def test_the_schema_the_ai_is_sent_does_not_mention_hiding():
    assert "hidden" not in json.dumps(LectureParts.model_json_schema())
    assert LectureSlide.model_fields["hidden"].default is False


def test_hiding_a_slide_leaves_it_out_of_the_deck_and_keeps_every_other_layout():
    source, knowledge, _ = figure_fixture()
    shown = lecture_page(source, knowledge, plan(), theme="maroon")
    hidden = plan()
    hidden.parts[0].slides[1].hidden = True
    after = lecture_page(source, knowledge, hidden, theme="maroon")
    editing = lecture_page(source, knowledge, hidden, theme="maroon", editable=True)
    layouts = LAYOUTS.findall(shown)
    assert after.count('class="slide-frame"') == shown.count('class="slide-frame"') - 1 and "Hai" not in after.split("<main")[1]
    # The hidden slide still takes its turn in the rotation: every other slide keeps the frame it had.
    assert LAYOUTS.findall(after) == layouts[:6] + layouts[7:]
    # The editor shows it dimmed and marks every frame with its place.
    assert LAYOUTS.findall(editing) == layouts
    assert '<article class="slide-frame" id="slide-7" data-slide="0.1" data-hidden="true"' in editing
    assert 'data-slide="1.1"' in editing and 'data-divider="1"' in editing and "data-hidden" not in after


def test_hide_show_delete_duplicate_and_add_change_the_saved_plan_and_the_deck(tmp_path):
    store, generation, folder = saved_deck(tmp_path)
    (folder / PHONE_PAGE).write_text("shared before", encoding="utf-8")
    assert op(store, generation, folder, "hide", slide=[0, 1])["at"] == "0.1"
    assert json.loads((folder / "lecture.json").read_text(encoding="utf-8"))["parts"][0]["slides"][1]["hidden"] is True
    assert "Hai" not in (folder / "lecture.html").read_text(encoding="utf-8").split("<main")[1]
    assert 'data-mode="phone"' in (folder / PHONE_PAGE).read_text(encoding="utf-8")  # a shared phone copy follows
    op(store, generation, folder, "show", slide=[0, 1])
    assert "Hai" in (folder / "lecture.html").read_text(encoding="utf-8")
    assert op(store, generation, folder, "duplicate", slide=[0, 0])["at"] == "0.1"
    assert titles(folder)[0] == ["Một", "Một", "Hai", "So sánh"]
    assert op(store, generation, folder, "delete", slide=[0, 1])["at"] == "0.0"
    added = op(store, generation, folder, "add", part=1, index=1)
    assert added["at"] == "1.1" and titles(folder)[1] == ["Một shot", "Slide mới", "Năm"]
    # A new slide teaches the ideas of the slide before it, so it stays grounded in the source.
    new = json.loads((folder / "lecture.json").read_text(encoding="utf-8"))["parts"][1]["slides"][1]
    assert new["unit_ids"] == ["shot", "control_chart"] and new["layout"] == "points" and new["points"] == ["Nhập ý của bạn ở đây."]
    assert 'data-slide="1.1"' in edit_page(store, generation)


def test_a_part_keeps_one_to_six_slides(tmp_path):
    store, generation, folder = saved_deck(tmp_path)
    op(store, generation, folder, "delete", slide=[1, 0])
    for refused in ({"type": "delete", "slide": [1, 0]}, {"type": "move", "slide": [1, 0], "to": [0, 0]}):
        with pytest.raises(EditError, match="keeps at least one slide"):
            op(store, generation, folder, refused.pop("type"), **refused)
    for _ in range(3):
        op(store, generation, folder, "add", part=0)
    for refused in ({"type": "add", "part": 0}, {"type": "duplicate", "slide": [0, 0]}):
        with pytest.raises(EditError, match="at most 6"):
            op(store, generation, folder, refused.pop("type"), **refused)
    op(store, generation, folder, "add", part=1)
    with pytest.raises(EditError, match="at most 6"):
        op(store, generation, folder, "move", slide=[1, 0], to=[0, 0])
    assert [len(part) for part in titles(folder)] == [6, 2]


def test_moving_a_slide_within_and_across_parts(tmp_path):
    store, generation, folder = saved_deck(tmp_path)
    assert op(store, generation, folder, "move", slide=[0, 0], to=[0, 2])["at"] == "0.2"
    assert titles(folder)[0] == ["Hai", "So sánh", "Một"]
    assert op(store, generation, folder, "move", slide=[0, 2], to=[1, 1])["at"] == "1.1"
    assert titles(folder) == [["Hai", "So sánh"], ["Một shot", "Một", "Năm"]]
    for bad in ({"slide": [0, 0], "to": [5, 0]}, {"slide": [0, 0], "to": [1, 9]}, {"slide": [7, 0], "to": [0, 0]}):
        with pytest.raises(EditError):
            op(store, generation, folder, "move", **bad)
    assert titles(folder) == [["Hai", "So sánh"], ["Một shot", "Một", "Năm"]]


def test_text_changes_not_saved_yet_travel_with_the_edit_and_a_refused_edit_changes_nothing(tmp_path):
    store, generation, folder = saved_deck(tmp_path)
    op(store, generation, folder, "hide", changes=[{"field": "parts.0.slides.0.title", "span": "", "text": "Mới"}], slide=[0, 2])
    assert titles(folder)[0][0] == "Mới"
    records = [(folder / name).read_bytes() for name in ("lecture.json", "knowledge.json", "lecture.html", HISTORY)]
    with pytest.raises(EditError, match="empty"):
        op(store, generation, folder, "delete", changes=[{"field": "parts.0.slides.0.title", "span": "", "text": " "}], slide=[0, 1])
    with pytest.raises(EditError, match="changed in another window") as stale:
        structure(store, generation, "0" * 16, [], {"type": "delete", "slide": [0, 1]})
    assert stale.value.status == 409
    with pytest.raises(EditError, match="no longer in the deck"):
        op(store, generation, folder, "delete", slide=[0, 9])
    assert [(folder / name).read_bytes() for name in ("lecture.json", "knowledge.json", "lecture.html", HISTORY)] == records


def test_undo_and_redo_restore_the_plan_and_the_part_titles(tmp_path):
    store, generation, folder = saved_deck(tmp_path)
    original = json.loads((folder / "lecture.json").read_text(encoding="utf-8"))
    op(store, generation, folder, "delete", slide=[0, 1])
    op(store, generation, folder, "move", slide=[0, 0], to=[1, 0],
       changes=[{"field": "chapters.0.title", "span": "", "text": "Phần mới"}])
    assert json.loads((folder / "knowledge.json").read_text(encoding="utf-8"))["chapters"][0]["title"] == "Phần mới"
    assert edit_page(store, generation).count('<meta name="distill-history" content="2,0">') == 1
    assert op(store, generation, folder, "undo")["history"] == {"undo": 1, "redo": 1}
    assert json.loads((folder / "knowledge.json").read_text(encoding="utf-8"))["chapters"][0]["title"] == "Rang cà phê"
    assert titles(folder)[0] == ["Một", "So sánh"]
    op(store, generation, folder, "undo")
    assert json.loads((folder / "lecture.json").read_text(encoding="utf-8")) == original
    with pytest.raises(EditError, match="nothing to undo"):
        op(store, generation, folder, "undo")
    assert op(store, generation, folder, "redo")["history"] == {"undo": 1, "redo": 1}
    assert titles(folder)[0] == ["Một", "So sánh"]
    # A new edit ends the redo path; a text save is a step too.
    op(store, generation, folder, "hide", slide=[0, 0])
    assert load_history(folder)["redo"] == []
    op(store, generation, folder, "undo")
    assert json.loads((folder / "lecture.json").read_text(encoding="utf-8"))["parts"][0]["slides"][0]["hidden"] is False


def test_history_keeps_twenty_steps_and_is_dropped_when_the_deck_is_made_again(tmp_path):
    store, generation, folder = saved_deck(tmp_path)
    for step in range(23):
        op(store, generation, folder, "hide" if step % 2 == 0 else "show", slide=[0, 0])
    assert len(load_history(folder)["undo"]) == 20
    (folder / "lecture.json").write_text((folder / "lecture.json").read_text(encoding="utf-8").replace("Một shot", "Một phát"), encoding="utf-8")
    assert load_history(folder)["undo"] == []  # the records changed outside the editor, so its steps no longer apply


def test_changing_a_layout_converts_the_content_and_says_what_it_cuts(tmp_path):
    store, generation, folder = saved_deck(tmp_path)
    _, knowledge, _ = figure_fixture()
    labelled = plan().parts[0].slides[0].model_dump(mode="json")
    timeline, warnings = deck_convert.convert(knowledge, labelled, "timeline")
    assert [(e["label"], e["text"]) for e in timeline["entries"]] == [("Nạp", "đổ hạt vào"), ("Sấy", "hạt mất nước"), ("Nâu", "Maillard")]
    assert warnings == [] and timeline["points"] == [] and timeline["unit_ids"] == ["charge"]
    # Unlabelled points are numbered, three points hold in two columns only by merging, and a table is read across.
    plain = plan().parts[0].slides[1].model_dump(mode="json")
    numbered, numbered_warnings = deck_convert.convert(knowledge, plain, "timeline")
    assert [e["label"] for e in numbered["entries"]] == ["1", "2", "3"] and "numbers" in numbered_warnings[0]
    compare, merged = deck_convert.convert(knowledge, plain, "compare")
    assert len(compare["columns"]) == 2 and any("merged into the last column" in warning for warning in merged)
    # Grounding rules still decide: a stats slide needs figures the source states, a quote needs original evidence.
    with pytest.raises(deck_convert.Unavailable, match="figures the source states"):
        deck_convert.convert(knowledge, labelled, "stats")
    stats = plan().parts[1].slides[0].model_dump(mode="json")
    points, _ = deck_convert.convert(knowledge, stats, "points")
    assert points["points"] == ["36 g: Khối lượng", "28 giây: Thời gian"]
    assert deck_convert.convert(knowledge, points, "stats")[0]["entries"] == stats["entries"]
    with pytest.raises(deck_convert.Unavailable, match="at least"):
        deck_convert.convert(knowledge, stats, "pyramid")
    options = {entry["layout"]: entry for entry in deck_convert.options(knowledge, labelled)}
    assert options["points"]["current"] and options["timeline"]["available"] and not options["stats"]["available"]
    assert options["stats"]["reason"] and set(options) == set(deck_convert.LAYOUTS)
    # Applied, the new layout is saved and drawn; the slide keeps its title, notes and ideas.
    result = op(store, generation, folder, "layout", slide=[0, 0], layout="timeline")
    assert result["at"] == "0.0"
    assert json.loads((folder / "lecture.json").read_text(encoding="utf-8"))["parts"][0]["slides"][0]["entries"][0] == {"label": "Nạp", "text": "đổ hạt vào"}
    with pytest.raises(EditError, match="figures the source states"):
        op(store, generation, folder, "layout", slide=[0, 0], layout="stats")


def test_the_editor_calls_the_structure_routes(tmp_path):
    app = create_app(tmp_path)
    store = app.state.store
    deck, page = made(store, "lecture"), made(store, "page")
    with TestClient(app, base_url="http://127.0.0.1") as client:
        headers = {"x-distill": app.state.csrf_token}
        editing = client.get(f"/api/generations/{deck}/slides/edit").text
        version = re.search(r'name="distill-version" content="(\w+)"', editing)[1]
        first = re.search(r'data-slide="(\d+)\.(\d+)"', editing)
        part, place = int(first[1]), int(first[2])
        url = f"/api/generations/{deck}/slides/structure"
        body = {"version": version, "op": {"type": "hide", "slide": [part, place]}}
        assert client.post(url, json=body).status_code == 403
        assert client.post(f"/api/generations/{page}/slides/structure", json=body, headers=headers).status_code == 409
        done = client.post(url, json=body, headers=headers)
        assert done.status_code == 200 and done.json()["at"] == f"{part}.{place}" and done.json()["history"] == {"undo": 1, "redo": 0}
        assert f'data-slide="{part}.{place}" data-hidden="true"' in client.get(f"/api/generations/{deck}/slides/edit").text
        assert 'data-hidden' not in client.get(f"/api/generations/{deck}/page").text
        stale = client.post(url, json=body, headers=headers)
        assert stale.status_code == 409 and "another window" in stale.json()["detail"]
        assert client.post(url, json={"version": done.json()["version"], "op": {"type": "teleport"}}, headers=headers).status_code == 422
        undone = client.post(url, json={"version": done.json()["version"], "op": {"type": "undo"}}, headers=headers)
        assert undone.json()["history"] == {"undo": 0, "redo": 1} and undone.json()["at"] is None
        options = client.get(f"/api/generations/{deck}/slides/layout-options", params={"slide": f"{part}.{place}"})
        assert options.status_code == 200 and {entry["layout"] for entry in options.json()["options"]} == set(deck_convert.LAYOUTS)
        current = next(entry for entry in options.json()["options"] if entry["current"])["layout"]
        other = next(entry for entry in options.json()["options"] if entry["available"])["layout"]
        preview = client.get(f"/api/generations/{deck}/slides/layout-preview", params={"slide": f"{part}.{place}", "layout": other})
        assert preview.status_code == 200 and preview.headers["content-security-policy"].startswith("sandbox allow-scripts")
        assert f'.slide-frame:not([data-slide="{part}.{place}"])' in preview.text and current != other
        assert client.get(f"/api/generations/{deck}/slides/layout-preview", params={"slide": "9.9", "layout": other}).status_code == 409
        assert client.get(f"/api/generations/{deck}/slides/layout-options", params={"slide": "x"}).status_code == 422
