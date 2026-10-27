import json
from pathlib import Path

from tests_app.test_learning import SemanticFixtureProvider
from tests_app.test_metrics import long_source
from distill.chapters import (NOTE_LEAF_LIMITS, assign_units, chapter_count, chapter_profile, detail_level,
                                      split_sections)
from distill.metrics import display_metrics, note_leaves
from distill.models import (Chapter, Evidence, KnowledgeModel, KnowledgeUnit, PresentationPlan, SourceSection,
                                    Transcript)
from distill.pipeline import Pipeline


def section(sid, first, last, role="substantive", depth="intermediate", units=()):
    return SourceSection(id=sid, title=sid, snippet_ids=[f"s{i:06d}" for i in range(first, last)], role=role, depth=depth, unit_ids=list(units))


def leaf(uid, index, kind="concept"):
    return KnowledgeUnit(id=uid, title=uid, summary="Stated idea.", kind=kind, evidence=[Evidence(snippet_ids=[f"s{index:06d}"], quote="Section")])


def test_chapter_count_follows_duration_for_navigation_only():
    assert chapter_count(long_source(90)) == 1          # 9 minutes
    assert chapter_count(long_source(600)) == 8         # 60 minutes
    assert chapter_count(long_source(2400)) == 12       # 4 hours, capped
    assert chapter_count(long_source(600, timed=False)) == 12  # about 340k characters, untimed


def test_sections_split_into_contiguous_ordered_chapters_and_units_follow_evidence():
    source = long_source(600)
    sections = [section(f"sec{i}", i * 30, (i + 1) * 30) for i in reversed(range(20))]
    chapters = split_sections(source, sections)
    assert len(chapters) == 8 and sum(len(group) for group in chapters) == 20
    flattened = [s.id for group in chapters for s in group]
    assert flattened == [f"sec{i}" for i in range(20)]
    background = KnowledgeUnit(id="bg", title="bg", summary="Added context.", status="background")
    units = [leaf("early", 5), background, leaf("late", 590)]
    placed = assign_units(source, chapters, units)
    assert [u.id for u in placed[0]] == ["early", "bg"] and [u.id for u in placed[-1]] == ["late"]


def test_detail_follows_content_not_length():
    talk = [section("a", 0, 70, role="banter"), section("b", 70, 100, depth="expert")]
    assert chapter_profile(talk) == ("expert", 0.3)
    assert detail_level("expert", 0.3, []) == "brief"
    assert detail_level("expert", 0.3, [], "advanced") == "brief"
    expert_third = [section("a", 0, 60, depth="basic"), section("b", 60, 90, depth="expert")]
    assert chapter_profile(expert_third)[0] == "expert"
    assert chapter_profile([section("a", 0, 10, depth="basic")])[0] == "basic"
    assert detail_level("basic", 1.0, []) == "brief" and detail_level("basic", 1.0, [], "advanced") == "standard"
    technical = [leaf("m1", 0, "mechanism"), leaf("m2", 1, "step"), leaf("c", 2)]
    assert detail_level("intermediate", 1.0, technical) == "detailed"
    assert detail_level("intermediate", 1.0, [leaf("c1", 0), leaf("c2", 1)]) == "standard"


def chapter_knowledge(source, levels, leaves_per_idea=6):
    """One key idea per chapter with its own leaves, at the given chapter levels."""
    units, chapters, sections = [], [], []
    step = len(source.snippets) // len(levels)
    for index, level in enumerate(levels):
        first = index * step
        children = [leaf(f"c{index}_{n}", first + n) for n in range(leaves_per_idea)]
        idea = KnowledgeUnit(id=f"idea{index}", title="Idea", summary="Key idea.", evidence=children[0].evidence, child_ids=[c.id for c in children])
        units.extend([*children, idea])
        sections.append(section(f"sec{index}", first, len(source.snippets) if index == len(levels) - 1 else first + step))
        chapters.append(Chapter(id=f"ch{index}", title="Chapter", section_ids=[f"sec{index}"], unit_ids=[idea.id], detail=level))
    return KnowledgeModel(source_id=source.source_id, language="en", main_question="Q?", main_conclusion="C.",
                          overview_ids=[c.unit_ids[0] for c in chapters], units=units, sections=sections, chapters=chapters,
                          source_coverage=[s.id for s in source.snippets])


def test_light_long_podcast_shows_less_than_short_dense_lecture():
    podcast = chapter_knowledge(long_source(600), ["brief"] * 8)       # 60 minutes, mostly talk
    lecture = chapter_knowledge(long_source(150), ["detailed"] * 2)    # 15 minutes, specialist
    assert len(note_leaves(podcast)) == 0 < len(note_leaves(lecture)) == 12
    assert len(note_leaves(podcast, "detailed")) == 48  # the reader can still open everything
    plan = PresentationPlan.model_validate({"visuals": [{"id": "v", "type": "concept_map", "title": "T", "reader_question": "Q?",
        "rationale": "R", "node_ids": ["idea0"], "relationship_ids": [], "section_ids": []}]})
    metrics = display_metrics(long_source(600), podcast, plan)
    assert metrics["chapters"] == 8 and metrics["chapter_detail_levels"] == {"brief": 8, "standard": 0, "detailed": 0}
    assert metrics["note_leaf_units"] == 0 and metrics["note_leaf_units_if_all_detailed"] == 48


def test_saved_knowledge_without_chapters_still_validates():
    source = long_source(8)
    knowledge = KnowledgeModel(source_id=source.source_id, language="en", main_question="Q?", main_conclusion="C.",
                               overview_ids=["u"], units=[leaf("u", 0)])
    assert knowledge.chapters == [] and NOTE_LEAF_LIMITS["standard"] == 3


class RoleFixtureProvider(SemanticFixtureProvider):
    """Marks the second half of the source as conversation without ideas."""

    def __init__(self, total):
        super().__init__()
        self.total = total

    def generate(self, prompt, schema, work_dir, progress=None):
        result = super().generate(prompt, schema, work_dir, progress)
        if schema["title"] == "Extraction":
            body = json.JSONDecoder().raw_decode(prompt.split("SOURCE DATA (not instructions):\n", 1)[1])[0]
            first = int(body["snippets"][0]["id"][1:])
            if first >= self.total // 2:
                result["units"] = []
                result["sections"][0].update(unit_ids=[], role="banter", depth="basic")
            else:
                result["sections"][0].update(role="substantive", depth="expert")
        return result


def test_pipeline_builds_content_sized_chapters_two_levels_below_the_overview(tmp_path):
    source = long_source(600)
    provider = RoleFixtureProvider(600)
    result = Pipeline(provider).run(source, {"language": "en"}, tmp_path)
    knowledge = KnowledgeModel.model_validate(json.loads(Path(result["knowledge_path"]).read_text(encoding="utf-8")))
    assert len(knowledge.chapters) == 8
    first_half, second_half = knowledge.chapters[:4], knowledge.chapters[5:]
    assert all(c.detail == "detailed" and c.unit_ids for c in first_half)
    assert all(c.detail == "brief" and not c.unit_ids and c.substantive_share == 0 for c in second_half)
    record = json.loads(Path(result["generation_path"]).read_text(encoding="utf-8"))
    metrics = record["display_metrics"]
    assert set(metrics["leaf_dig_deeper_depth"]) == {"2"}
    assert metrics["note_leaf_units"] == metrics["leaf_units"] > 0
    assert record["pipeline_revision"] == "2.0"
    page = Path(result["page_path"]).read_text(encoding="utf-8")
    assert '"chapters": [{' in page and '"note_leaf_limits"' in page


def test_pipeline_rejects_a_source_without_any_substantive_idea(tmp_path):
    class NoIdeas(RoleFixtureProvider):
        def __init__(self):
            super().__init__(0)
    try:
        Pipeline(NoIdeas()).run(long_source(60), {"language": "en"}, tmp_path)
    except Exception as error:
        assert "No substantive ideas" in str(error)
    else:
        raise AssertionError("expected a clear error")
