import json
from pathlib import Path

from tests_app.learning_fixture import fixture
from tests_app.test_learning import SemanticFixtureProvider
from distill.metrics import display_metrics, evenly_spaced, source_positions, spread_by_source_position
from distill.models import Evidence, KnowledgeModel, KnowledgeUnit, PresentationPlan, Transcript
from distill.pipeline import Pipeline


def cited(uid, sid, kind="mechanism", children=None):
    return KnowledgeUnit(id=uid, title=uid, summary="Stated idea.", kind=kind, status="source",
                         evidence=[Evidence(snippet_ids=[sid], quote="idea")], child_ids=children or [])


def long_source(count, timed=True):
    original, _, _ = fixture()
    return Transcript.model_validate({**original.model_dump(), "content_hash": "", "snippets": [
        {"id": f"s{i:06d}", "text": f"Section {i} states an important idea. " + "Evidence from the source. " * 20,
         **({"start": i * 6.0, "end": i * 6.0 + 6} if timed else {})} for i in range(count)]})


def test_evenly_spaced_keeps_order_ends_and_limit():
    assert evenly_spaced(list(range(10)), 4) == [0, 3, 6, 9]
    assert evenly_spaced(list(range(3)), 5) == [0, 1, 2]
    assert evenly_spaced(list(range(5)), 1) == [0] and evenly_spaced(list(range(5)), 0) == []


def test_spread_selects_across_the_whole_source_not_its_opening():
    source = long_source(100)
    positions = source_positions(source)
    units = [cited(f"u{i}", f"s{i * 2:06d}") for i in range(50)]
    chosen = spread_by_source_position(units, positions, 12)
    assert len(chosen) == 12
    quarters = [min(3, int(positions[u.evidence[0].snippet_ids[0]] * 4)) for u in chosen]
    assert set(quarters) == {0, 1, 2, 3} and quarters == sorted(quarters)
    background = KnowledgeUnit(id="bg", title="bg", summary="Added context.", status="background")
    assert spread_by_source_position([units[0], background], positions, 12) == [units[0], background]


def test_display_metrics_report_visibility_depth_and_source_placement():
    source = long_source(8)
    leaves = [cited(f"leaf{i}", f"s{i:06d}") for i in range(8)]
    middle = [cited("early", "s000000", "concept", ["leaf0", "leaf1", "leaf2", "leaf3"]),
              cited("late", "s000004", "concept", ["leaf4", "leaf5", "leaf6", "leaf7"])]
    top = cited("top", "s000000", "concept", ["early", "late"])
    knowledge = KnowledgeModel(source_id=source.source_id, language="en", main_question="Q?", main_conclusion="C.",
                               overview_ids=["top"], units=[*leaves, *middle, top])
    presentation = PresentationPlan.model_validate({"visuals": [{"id": "v", "type": "concept_map", "title": "T",
        "reader_question": "Q?", "rationale": "R", "node_ids": ["top", "leaf0", "leaf1"], "relationship_ids": [], "section_ids": []}]})
    metrics = display_metrics(source, knowledge, presentation)
    assert metrics["source_minutes"] == 0.8 and metrics["overview_ideas"] == 1
    assert metrics["leaf_units"] == 8 and metrics["visible_nodes"] == 3 and metrics["visible_leaf_units"] == 2
    assert metrics["leaf_units_by_source_quarter"] == [2, 2, 2, 2]
    assert metrics["visible_nodes_by_source_quarter"] == [3, 0, 0, 0]
    assert metrics["leaf_dig_deeper_depth"] == {"2": 8}
    untimed = display_metrics(long_source(8, timed=False), knowledge, presentation)
    assert untimed["source_minutes"] is None and untimed["visible_nodes_per_10_minutes"] is None


class DetailFixtureProvider(SemanticFixtureProvider):
    """Extracts one mechanism per window and records the presentation request."""

    def generate(self, prompt, schema, work_dir, progress=None):
        result = super().generate(prompt, schema, work_dir, progress)
        if schema["title"] == "Extraction":
            result["units"][0]["kind"] = "mechanism"
        if schema["title"] == "PresentationPlan":
            self.presentation_body = json.JSONDecoder().raw_decode(prompt.split("SOURCE DATA (not instructions):\n", 1)[1])[0]
        return result


def test_presentation_receives_detail_from_the_end_of_a_long_source(tmp_path):
    source = long_source(600)
    provider = DetailFixtureProvider()
    result = Pipeline(provider).run(source, {"language": "en"}, tmp_path)
    assert provider.calls.count("Extraction") > 12
    positions = source_positions(Transcript.model_validate(json.loads(Path(result["source_path"]).read_text(encoding="utf-8"))))
    knowledge = json.loads(Path(result["knowledge_path"]).read_text(encoding="utf-8"))
    units = {u["id"]: u for u in knowledge["units"]}
    offered = [units[u["id"]] for u in provider.presentation_body["units"] if u["kind"] == "mechanism"]
    starts = [positions[u["evidence"][0]["snippet_ids"][0]] for u in offered]
    assert len(offered) == 12 and max(starts) >= 0.75 and min(starts) < 0.25
    record = json.loads(Path(result["generation_path"]).read_text(encoding="utf-8"))
    assert record["presentation_revision"] == "2"
    assert (tmp_path / "checkpoints" / "presentation_r2.json").is_file()
    metrics = record["display_metrics"]
    assert metrics["leaf_units"] == provider.calls.count("Extraction")
    assert sum(metrics["leaf_units_by_source_quarter"]) == metrics["leaf_units"]
    assert all(metrics["leaf_units_by_source_quarter"]) and metrics["source_minutes"] == 60.0
