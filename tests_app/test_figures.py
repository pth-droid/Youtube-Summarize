"""Process figures: fixed forms filled from validated knowledge, drawn in the theme, never inventing geometry."""
import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from distill.apparatus import TEMPLATES, catalogue
from distill.models import FigurePlan, validate_figures
from distill.pipeline import Pipeline
from distill.renderer import render_lecture, render_page
from tests_app.figure_fixture import EXTRACTION, ROAST, figure_fixture, figure_lecture as lecture, figure_plans
from tests_app.learning_fixture import fixture
from tests_app.test_learning import SemanticFixtureProvider


def plan_with(change, base=ROAST):
    data = copy.deepcopy(base)
    change(data["figures"])
    return FigurePlan.model_validate(data)


def test_figure_contracts_accept_the_authored_plans_and_reject_invented_geometry():
    _, knowledge, _ = figure_fixture()
    for plan in figure_plans():
        validate_figures(knowledge, plan)

    def reject(change, message, base=ROAST, error=ValueError):
        with pytest.raises(error, match=message):
            validate_figures(knowledge, plan_with(change, base))

    reject(lambda f: f[0]["unit_ids"].append("invented"), "not supplied")
    reject(lambda f: f[1]["apparatus"]["parts"].append({"slot": "steam_wand", "label": "Vòi hơi", "note": "", "unit_ids": []}), "distinct slots")
    reject(lambda f: f[1]["apparatus"]["flows"].append({"path": "charge", "kind": "water", "label": "Nước", "unit_ids": ["heat"]}), "allowed kinds")
    reject(lambda f: f[2]["what_if"]["levers"].append({"unit_id": "first_crack_time", "label": "Nứt"}), "cause of at least one")
    reject(lambda f: f[2]["what_if"]["effects"].append({"relationship_id": "missing", "direction": "increases"}), "causes")

    def schema_reject(change, message, base=ROAST):
        with pytest.raises(ValidationError, match=message):
            plan_with(change, base)

    schema_reject(lambda f: f[0]["process"]["compounds"][0]["levels"].pop(), "one level per phase")
    schema_reject(lambda f: f[0]["process"]["phases"][1].update(start=200), "without overlapping")
    schema_reject(lambda f: f[0]["process"]["series"][0]["points"].reverse(), "increasing x order")
    schema_reject(lambda f: f[0]["process"]["series"].extend(
        {"id": f"extra{i}", "label": "Extra", "unit": f"u{i}", "provenance": "source", "unit_ids": ["heat"], "points": [{"x": 0, "y": 1}, {"x": 10, "y": 2}]} for i in range(3)),
        "at most three panels")
    schema_reject(lambda f: f[2]["region_map"]["regions"][1].update(x_max=40), "inside the map axes", base=EXTRACTION)
    schema_reject(lambda f: f[2]["region_map"]["regions"][1].update(emphasis=True), "at most one region", base=EXTRACTION)
    schema_reject(lambda f: f[3].update(apparatus=f[1]["apparatus"]), "exactly the specification")
    schema_reject(lambda f: f[0]["process"].update(series=[], states=[], compounds=[]), "phases alone belong in the text")

    knowledge.units.append(knowledge.units[0].model_copy(update={"id": "added", "status": "background", "evidence": []}))
    with pytest.raises(ValueError, match="original evidence"):
        validate_figures(knowledge, plan_with(lambda f: f[0]["process"]["series"][0].update(unit_ids=["added"])))


def test_apparatus_templates_keep_their_geometry_out_of_the_model_request():
    listed = catalogue()
    assert set(listed) == set(TEMPLATES) == {"drum_roaster", "espresso", "pour_over"}
    json.dumps(listed)
    # Descriptions, slot IDs and path kinds only: no coordinates or path data reach the model.
    for item in listed.values():
        assert set(item) == {"description", "slots", "paths"} and all(isinstance(text, str) for text in item["slots"].values())
        assert all(set(path) == {"description", "kinds"} for path in item["paths"].values())
    for template in TEMPLATES.values():
        assert all(0 <= value["at"][0] <= 800 and 0 <= value["at"][1] <= 500 for value in template["slots"].values())
        assert all(path["kinds"] and path["d"] for path in template["paths"].values())
        assert "<script" not in template["draw"]()


def test_page_places_figures_with_their_tables_and_escapes_text(tmp_path):
    source, knowledge, presentation = figure_fixture()
    data = copy.deepcopy(ROAST)
    data["figures"][0]["title"] = "<script>alert(1)</script>"
    data["figures"][0]["process"]["phases"][0]["note"] = "</script><img src=x onerror=alert(1)>"
    page = render_page(source, knowledge, presentation, tmp_path / "page.html", FigurePlan.model_validate(data)).read_text(encoding="utf-8")
    assert "<script>alert(1)" not in page and "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    blobs = [part.split("</script>", 1)[0] for part in page.split('<script type="application/json" class="figure-data">')[1:]]
    assert len(blobs) == 2 and all("</" not in blob for blob in blobs)  # the process and what-if figures; the others are static
    assert json.loads(blobs[0])["phases"][0]["note"].startswith("</script>")
    assert page.index('id="visuals"') < page.index('id="process-figures"') < page.index('id="detail-panel"')
    assert page.count('class="visual-section figure-section"') == 4
    for marker in ('data-figure="process"', 'data-figure="apparatus"', 'data-figure="what_if"', 'data-figure="scale_ladder"',
                   'class="fig-state"', 'class="fig-data"', 'data-select-unit="chemistry"', 'class="flow flow-radiation"'):
        assert marker in page
    assert "11% → 2%" in page and "Đèn halogen" in page and "Hình dáng minh họa" in page
    assert "--fig-1:#00897b" in page and "<script src=" not in page and "<link" not in page

    plain = render_page(source, knowledge, presentation, tmp_path / "plain.html").read_text(encoding="utf-8")
    assert "fig-1" not in plain and "pythonLiteral" not in plain  # figure assets only travel with figures


def test_lecture_places_each_figure_after_its_chapter(tmp_path):
    source, knowledge, _ = figure_fixture()
    roast, extraction = figure_plans()
    deck = render_lecture(source, knowledge, lecture(), tmp_path / "roast.html", roast).read_text(encoding="utf-8")
    kinds = [chunk.split('"', 1)[0] for chunk in deck.split('class="slide kind-')[1:]]
    first_part = kinds.index("points")
    # Part 1 slide, then the timeline, the states slide, the roaster, the levers and the scale ladder.
    assert kinds[first_part + 1:first_part + 6] == ["figure"] * 5
    assert kinds[first_part + 6] == "divider" and kinds.count("figure") == 5
    assert "Hạt cà phê thay đổi thế nào" in deck and 'class="fig-compounds"' in deck
    assert deck.count('data-key="fig1"') == 2  # the chart and the states slide move together

    deck = render_lecture(source, knowledge, lecture(), tmp_path / "brew.html", extraction).read_text(encoding="utf-8")
    kinds = [chunk.split('"', 1)[0] for chunk in deck.split('class="slide kind-')[1:]]
    second_part = len(kinds) - 1 - kinds[::-1].index("points")
    assert kinds[second_part + 1:second_part + 5] == ["figure"] * 4 and kinds[second_part + 5] == "recap"
    assert "So với log" not in deck  # a presented deck has no file reader


def test_ordered_phases_show_no_numbers_and_a_band_only_chart_shares_its_slide(tmp_path):
    source, knowledge, presentation = figure_fixture()
    data = copy.deepcopy(ROAST)
    process = data["figures"][0]["process"]
    process.update(axis="other", axis_label="Thứ tự", series=[], compounds=[], events=[])
    for index, phase in enumerate(process["phases"]):
        phase.update(start=index, end=index + 1)
    plan = FigurePlan.model_validate({"figures": data["figures"][:1]})
    page = render_page(source, knowledge, presentation, tmp_path / "page.html", plan).read_text(encoding="utf-8")
    assert 'class="fig-chart compact"' in page and '<p class="fig-state-time">01</p>' in page
    assert "<th scope=\"col\">Từ</th>" not in page  # positions in order are not values
    deck = render_lecture(source, knowledge, lecture(), tmp_path / "deck.html", plan).read_text(encoding="utf-8")
    assert deck.count('class="slide kind-figure"') == 1 and 'class="fig-state"' in deck


class FigureProvider(SemanticFixtureProvider):
    """Mechanism units, then a process figure built from whatever IDs the stage supplies."""
    def __init__(self, invalid_first=False):
        super().__init__()
        self.invalid_first = invalid_first

    def generate(self, prompt, schema, work_dir, progress=None):
        value = super().generate(prompt, schema, work_dir, progress)
        if schema["title"] == "Extraction":
            unit = value["units"][0]
            unit["kind"] = "mechanism"
            value["units"].append({**unit, "id": "leaf_two", "title": "Second mechanism"})
            value["sections"][0]["unit_ids"].append("leaf_two")
        if schema["title"] == "FigureSet":
            body = json.JSONDecoder().raw_decode(prompt.split("SOURCE DATA (not instructions):\n", 1)[1])[0]
            assert body["templates"]["drum_roaster"]["paths"]["radiant_heat"]["kinds"] == ["radiation"]
            ids = [u["id"] for u in body["units"]]
            if self.invalid_first and self.calls.count("FigureSet") == 1:
                ids = ["invented", *ids]
            value = {"figures": [{"id": "timeline", "type": "process", "title": "Phases", "reader_question": "What changes?", "caption": "",
                                  "unit_ids": ids[:2], "process": {"axis": "time", "axis_label": "Time", "axis_unit": "", "subject": "bean", "subject_label": "Bean",
                                  "phases": [{"id": "a", "label": "First", "start": 0, "end": 60, "note": "", "unit_ids": ids[:1]},
                                             {"id": "b", "label": "Second", "start": 60, "end": 120, "note": "", "unit_ids": ids[1:2]}],
                                  "events": [], "states": [], "compounds": [],
                                  "series": [{"id": "shape", "label": "Shape", "unit": "", "provenance": "illustrative", "unit_ids": ids[:1],
                                              "points": [{"x": 0, "y": 1}, {"x": 60, "y": 3}, {"x": 120, "y": 2}]}]},
                                  "apparatus": None, "region_map": None, "what_if": None, "scale_ladder": None}]}
        return value


def test_pipeline_adds_figures_once_and_reuses_them_for_slides(tmp_path):
    source, _, _ = fixture()
    provider = FigureProvider()
    result = Pipeline(provider).run(source, {"language": "en"}, tmp_path)
    assert provider.calls.count("FigureSet") == 1
    page = Path(result["page_path"]).read_text(encoding="utf-8")
    assert 'data-figure="process"' in page and "Illustrative shape: no real values" in page
    record = json.loads((tmp_path / "generation.json").read_text(encoding="utf-8"))
    assert record["figures"] == ["process"] and record["figure_revision"] == "1"
    assert FigurePlan.model_validate_json((tmp_path / "figures.json").read_text(encoding="utf-8")).figures

    calls = len(provider.calls)
    Pipeline(provider).run(source, {"language": "en"}, tmp_path)
    assert len(provider.calls) == calls  # the saved figure plan is reused
    Pipeline(provider).run(source, {"language": "en", "output_format": "lecture"}, tmp_path)
    assert provider.calls[calls:] == ["LectureParts", "LectureFrame"]
    assert 'class="slide kind-figure"' in (tmp_path / "lecture.html").read_text(encoding="utf-8")


def test_figure_stage_repairs_invalid_ideas_and_skips_sources_without_mechanisms(tmp_path):
    source, _, _ = fixture()
    provider = FigureProvider(invalid_first=True)
    Pipeline(provider).run(source, {"language": "en"}, tmp_path / "repaired")
    assert provider.calls.count("FigureSet") == 2
    assert 'data-figure="process"' in (tmp_path / "repaired" / "page.html").read_text(encoding="utf-8")

    plain = SemanticFixtureProvider()
    Pipeline(plain).run(source, {"language": "en"}, tmp_path / "plain")
    assert "FigureSet" not in plain.calls  # concept-only sources never pay for a figure request
    assert json.loads((tmp_path / "plain" / "figures.json").read_text(encoding="utf-8"))["figures"] == []

