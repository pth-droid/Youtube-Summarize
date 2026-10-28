"""Lecture slides: a second output from the same validated knowledge, without new analysis."""
import json
import re

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from distill.app import create_app
from distill.config import DEFAULT_SETTINGS
from distill.models import KnowledgeUnit, LectureColumn, LectureEntry, LecturePart, LecturePlan, LectureSlide, validate_lecture
from distill.pipeline import Pipeline
from distill.renderer import render_lecture
from distill.storage import Store
from distill.worker import Worker
from tests_app.figure_fixture import figure_fixture
from tests_app.learning_fixture import fixture
from tests_app.test_learning import SemanticFixtureProvider

ANALYSIS = ["Extraction", "GroundingReview", "Synthesis", "PresentationPlan"]


def slide(layout="points", ids=("u1",), **values):
    content = {"columns": [LectureColumn(heading="Light roast", points=["Origin character"]),
                           LectureColumn(heading="Dark roast", points=["Roast flavours"])]} if layout == "compare" else {"points": ["A short point"]}
    return LectureSlide(layout=layout, title=values.pop("title", "A teachable point"), unit_ids=list(ids), **(content | values))


def plan(*slides):
    return LecturePlan(title="Rang cà phê", objectives=["Explain heat.", "Compare roasts."], takeaways=["Heat matters.", "Origin matters."],
                       parts=[LecturePart(chapter_id="overview", slides=list(slides))])


def test_lecture_output_reuses_analysis_and_resumes_without_model_calls(tmp_path):
    source, _, _ = fixture()
    provider = SemanticFixtureProvider()
    page = Pipeline(provider).run(source, {"language": "en"}, tmp_path)
    assert page["output_format"] == "page" and page["page_path"].endswith("page.html")
    analysis_calls = list(provider.calls)
    assert set(ANALYSIS) <= set(analysis_calls)

    # The format is outside the analysis fingerprint: only the two lecture stages run.
    lecture = Pipeline(provider).run(source, {"language": "en", "output_format": "lecture"}, tmp_path)
    assert provider.calls[len(analysis_calls):] == ["LectureParts", "LectureFrame"]
    assert lecture["output_format"] == "lecture" and lecture["page_path"].endswith("lecture.html")
    record = json.loads((tmp_path / "generation.json").read_text(encoding="utf-8"))
    assert record["output_format"] == "lecture" and record["lecture_slides"] >= 1
    saved = LecturePlan.model_validate_json((tmp_path / "lecture.json").read_text(encoding="utf-8"))
    assert saved.parts

    # A frame saved while decks still ended in a quiz keeps its title, objectives and takeaways.
    frame = tmp_path / "checkpoints" / "lecture_r1_frame.json"
    old = json.loads(frame.read_text(encoding="utf-8"))
    old["data"]["questions"] = [{"question": "Old quiz question?", "options": ["A", "B"], "answer": 0, "explanation": "x", "unit_ids": ["parent"]}]
    frame.write_text(json.dumps(old), encoding="utf-8")
    calls = len(provider.calls)
    # The slide look is outside the fingerprint too: a new look only renders again.
    Pipeline(provider).run(source, {"language": "en", "output_format": "lecture", "slide_theme": "maroon"}, tmp_path)
    assert len(provider.calls) == calls  # saved lecture parts and frame are reused
    assert json.loads((tmp_path / "generation.json").read_text(encoding="utf-8"))["slide_theme"] == "maroon"

    deck = (tmp_path / "lecture.html").read_text(encoding="utf-8")
    assert 'data-look="maroon"' in deck
    assert deck.count('class="slide-frame"') >= 6
    assert "Explain the source model." in deck and "What does the source explain?" in deck
    # The deck is presented to a group: it has no quiz.
    assert "Old quiz question?" not in deck and "kind-quiz" not in deck and "Show answer" not in deck


def test_lecture_deck_escapes_text_shows_verbatim_quotes_and_source_times(tmp_path):
    source, knowledge, _ = fixture()
    knowledge.units[1].status = "inference"
    lecture = plan(slide(title="<script>alert(1)</script>", ids=("u1",)), slide("steps", ("u4",), points=["Heat", "Observe", "Stop"]),
                   slide("compare", ("u3",)), slide("quote", ("u2",), notes="Read the quote aloud."))
    deck = render_lecture(source, knowledge, lecture, tmp_path / "lecture.html").read_text(encoding="utf-8")

    assert "<script>alert(1)" not in deck and "&lt;script&gt;alert(1)&lt;/script&gt;" in deck
    assert "watch?v=L_Guz73e6fw&amp;t=60s" in deck and "▶ 1:00" in deck
    assert source.snippets[1].text in deck  # the quote slide and its notes show the original words
    # Each slide is drawn by a library layout its content fits: a comparison by headed columns, steps by a sequence.
    layouts = dict(re.findall(r'class="slide kind-(\w+) layout-([\w-]+) variant-\d"', deck))
    assert layouts["compare"] == "two-col-head" and layouts["steps"] in {"arrows", "timeline", "timeline-v", "bullets", "big-bullets"}
    assert "Suy luận" in deck and "Coffee origin also matters." in deck  # status and caveats stay visible
    assert 'data-look="forest"' in deck  # the look that matches the app, unless another is chosen
    unknown = render_lecture(source, knowledge, lecture, tmp_path / "other.html", theme='maroon" onload="alert(1)').read_text(encoding="utf-8")
    assert 'data-look="forest"' in unknown and "alert(1)\"" not in unknown
    assert deck.count('class="slide-frame"') == 2 + 1 + 4 + 1 + 1  # title, objectives, question, slides, recap, limits
    assert "BÀI GIẢNG" in deck and 'lang="vi"' in deck


def test_lecture_contracts_reject_unsupported_slides():
    _, knowledge, _ = fixture()
    with pytest.raises(ValueError, match="unknown ideas"):
        validate_lecture(knowledge, plan(slide(ids=("invented",))))
    knowledge.units.append(KnowledgeUnit(id="extra", title="Added context", summary="Background.", status="background"))
    with pytest.raises(ValueError, match="original evidence"):
        validate_lecture(knowledge, plan(slide("quote", ("extra",))))
    with pytest.raises(ValueError, match="unknown chapter"):
        validate_lecture(knowledge, plan(slide()).model_copy(update={"parts": [LecturePart(chapter_id="elsewhere", slides=[slide()])]}))
    with pytest.raises(ValidationError):
        LectureSlide(layout="compare", title="One side", unit_ids=["u1"], columns=[LectureColumn(heading="Only", points=["x"])])
    with pytest.raises(ValidationError):
        LectureSlide(layout="points", title="Empty", unit_ids=["u1"])


def test_structured_layouts_hold_their_own_shape_and_stats_quote_the_ideas():
    column = lambda *rows: LectureColumn(heading="Option", points=list(rows))
    entry = lambda label, text="What it means": LectureEntry(label=label, text=text)
    LectureSlide(layout="table", title="Across", unit_ids=["u1"], columns=[column("a", "b"), column("c", "d"), column("e", "f")])
    LectureSlide(layout="pyramid", title="Levels", unit_ids=["u1"], entries=[entry("Top"), entry("Middle"), entry("Base")])
    for wrong in ({"layout": "table", "columns": [column("a", "b"), column("c")]},  # rows must line up
                  {"layout": "columns", "columns": [column("a")]},  # two to four columns
                  {"layout": "funnel", "entries": [entry("Wide"), entry("Narrow")]},  # three to five stages
                  {"layout": "timeline", "entries": [entry("0:00"), entry("0:30")], "points": ["also bullets"]},
                  {"layout": "points", "points": ["x"], "entries": [entry("stray")]}):
        with pytest.raises(ValidationError):
            LectureSlide(title="Wrong", unit_ids=["u1"], **wrong)

    # A figure on a stats slide must be written in the ideas it cites; a decimal comma matches a point.
    _, knowledge, _ = figure_fixture()
    stats = lambda *labels: plan(LectureSlide(layout="stats", title="Một shot", unit_ids=["shot", "control_chart"], entries=[entry(label) for label in labels]))
    validate_lecture(knowledge, stats("36 g", "28 giây", "1,15–1,35% TDS"))
    with pytest.raises(ValueError, match="number its cited ideas state"):
        validate_lecture(knowledge, stats("36 g", "40 giây"))
    with pytest.raises(ValueError, match="number its cited ideas state"):
        validate_lecture(knowledge, stats("36 g", "Nhiều"))


def test_first_slides_for_a_video_reuse_its_page_analysis_but_new_versions_do_not(tmp_path, monkeypatch):
    provider = SemanticFixtureProvider()
    monkeypatch.setattr("distill.providers.make_provider", lambda *_args, **_kwargs: provider)
    app = create_app(tmp_path)
    store: Store = app.state.store
    source, _, _ = fixture()
    job = store.create_job({"kind": "youtube", "video_id": source.video_id, "preferences": store.settings()})
    store.checkpoint(job["id"], "source", source.model_dump(mode="json"))
    assert Worker(store).run_once()
    first = len(provider.calls)
    assert set(ANALYSIS) <= set(provider.calls)

    with TestClient(app, base_url="http://127.0.0.1") as client:
        headers = {"x-distill": app.state.csrf_token}
        url = f"https://www.youtube.com/watch?v={source.video_id}"
        existing = client.post("/api/jobs", json={"url": url, "preferences": {"output_format": "lecture"}}, headers=headers).json()
        assert existing["existing"] and existing["existing"][0]["metadata"]["output_format"] == "page"
        created = client.post("/api/jobs", json={"url": url, "preferences": {"output_format": "lecture"}, "regenerate": True}, headers=headers)
        assert created.status_code == 201
        assert Worker(store).run_once()
        assert provider.calls[first:] == ["LectureParts", "LectureFrame"]
        lecture = store.get_generation(store.get_job(created.json()["job"]["id"])["generation_id"])
        assert lecture["metadata"]["output_format"] == "lecture"
        exported = client.get(f"/api/generations/{lecture['id']}/export")
        assert "lecture-slides-" in exported.headers["content-disposition"] and 'class="slide-frame"' in exported.text

        # The same slides in another look reuse the analysis and the lecture plan: only rendering runs.
        calls = len(provider.calls)
        maroon = client.post("/api/jobs", json={"url": url, "preferences": {"output_format": "lecture", "slide_theme": "maroon"}, "regenerate": True}, headers=headers)
        assert maroon.status_code == 201 and Worker(store).run_once()
        assert provider.calls[calls:] == []
        recoloured = store.get_generation(store.get_job(maroon.json()["job"]["id"])["generation_id"])
        assert recoloured["metadata"]["slide_theme"] == "maroon"
        assert 'data-look="maroon"' in client.get(f"/api/generations/{recoloured['id']}/export").text

        second = len(provider.calls)
        again = client.post("/api/jobs", json={"url": url, "preferences": {"output_format": "lecture"}, "regenerate": True}, headers=headers)
        assert again.status_code == 201 and Worker(store).run_once()
        assert "Extraction" in provider.calls[second:]  # a new version of existing slides analyses again


def test_settings_default_output_and_new_page_override(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        headers = {"x-distill": app.state.csrf_token}
        assert client.get("/api/settings", headers=headers).json()["preferences"]["output_format"] == DEFAULT_SETTINGS["output_format"] == "page"
        saved = client.put("/api/settings", json={"output_format": "lecture"}, headers=headers).json()["preferences"]
        assert saved["output_format"] == "lecture"
        job = client.post("/api/jobs", json={"url": "https://youtu.be/L_Guz73e6fw", "preferences": {"output_format": "page"}}, headers=headers).json()["job"]
        assert job["input"]["preferences"]["output_format"] == "page"
        # The slide look: forest by default, saved like any preference, one of the known looks only.
        assert DEFAULT_SETTINGS["slide_theme"] == job["input"]["preferences"]["slide_theme"] == "forest"
        assert client.put("/api/settings", json={"slide_theme": "maroon"}, headers=headers).json()["preferences"]["slide_theme"] == "maroon"
        assert client.put("/api/settings", json={"slide_theme": "neon"}, headers=headers).status_code == 422


def test_every_look_the_presets_define_is_offered_with_its_swatch_and_drawn(tmp_path):
    from distill.looks import LOOKS_CSS, SLIDE_LOOKS, SLIDE_THEMES, SWATCH_TOKENS, look_tokens
    css = LOOKS_CSS.read_text(encoding="utf-8")
    # The app names exactly the looks the copied skill presets define, and each has a dark version for the screen.
    assert set(look_tokens(css)) == set(SLIDE_THEMES) == set(SLIDE_LOOKS) and len(SLIDE_THEMES) == 7
    assert all(f":root[data-look={look}][data-theme=dark]" in css for look in SLIDE_THEMES)
    app = create_app(tmp_path)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        headers = {"x-distill": app.state.csrf_token}
        looks = client.get("/api/settings", headers=headers).json()["looks"]
        assert [look["id"] for look in looks] == list(SLIDE_THEMES) and looks[0]["name"] == "Forest green"
        assert all(set(look["tokens"]) == set(SWATCH_TOKENS) and look["tokens"]["surface"].startswith("#") for look in looks)
        for look in SLIDE_THEMES:
            assert client.put("/api/settings", json={"slide_theme": look}, headers=headers).json()["preferences"]["slide_theme"] == look
    source, knowledge, _ = fixture()
    deck = render_lecture(source, knowledge, plan(slide()), tmp_path / "slate.html", theme="slate").read_text(encoding="utf-8")
    assert 'data-look="slate"' in deck and ":root[data-look=slate]{" in deck
    # Figures take the deck's look: the flow steps are its data series, the neutrals mix from its surfaces.
    assert "--fig-1:var(--data-1)" in deck and "--fig-metal:color-mix(" in deck


def test_layout_rotation_never_repeats_a_frame_and_fits_each_content_shape(tmp_path):
    from distill.deck_layouts import HEAVY
    from tests_app.variant_fixture import variant_fixture
    source, knowledge, lectures = variant_fixture()
    families = {"points": {"bullets", "big-bullets", "two-col", "three-col", "four-col", "text-boxes", "icons", "accent-left", "accent-right",
                           "accent-top", "accent-left-fit", "accent-right-fit", "small-icons"},
                "steps": {"bullets", "big-bullets", "arrows", "timeline", "timeline-v", "text-boxes"}, "timeline": {"timeline", "timeline-v", "arrows", "bullets"},
                "compare": {"two-col-head"}, "columns": {"three-col-head", "four-col", "text-boxes", "two-col-head"}, "table": {"table", "table-3row"},
                "pyramid": {"pyramid", "pyramid-outline", "pyramid-left"}, "funnel": {"funnel", "arrows", "bullets"},
                "stats": {"big-numbers", "circle-stats", "bar-stats", "text-boxes", "two-col-head", "bullets"}, "quote": {"quote"}}
    seen = set()
    for first, lecture in lectures.items():
        deck = render_lecture(source, knowledge, lecture, tmp_path / f"deck-{first}.html", theme="maroon").read_text(encoding="utf-8")
        frames = re.findall(r'class="slide kind-(\w+)(?: layout-([\w-]+) variant-(\d))?"', deck)
        drawn = [(layout, int(variant)) for _, layout, variant in frames if layout]
        for before, after in zip(drawn, drawn[1:]):
            assert before != after and not (before in HEAVY and after in HEAVY)
        for one, two, three in zip(drawn, drawn[1:], drawn[2:]):
            assert not one[0] == two[0] == three[0], "a layout ran three slides in a row"
        for kind, layout, _ in frames:
            assert kind == "figure" or kind not in families or layout in families[kind], (kind, layout)
        seen |= set(drawn)
        assert "layout-big-numbers" in deck and 'class="levels"' in deck  # data layouts travel with their stylesheet
        assert ".layout-funnel" in deck
    # Across four decks the rotation reaches many frames, not one per kind.
    assert len({layout for layout, _ in seen}) >= 18 and len(seen) >= 50
