"""Lecture slides: a second output from the same validated knowledge, without new analysis."""
import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from distill.app import create_app
from distill.config import DEFAULT_SETTINGS
from distill.models import KnowledgeUnit, LectureColumn, LecturePart, LecturePlan, LectureQuestion, LectureSlide, validate_lecture
from distill.pipeline import Pipeline
from distill.renderer import render_lecture
from distill.storage import Store
from distill.worker import Worker
from tests_app.learning_fixture import fixture
from tests_app.test_learning import SemanticFixtureProvider

ANALYSIS = ["Extraction", "GroundingReview", "Synthesis", "PresentationPlan"]


def slide(layout="points", ids=("u1",), **values):
    content = {"columns": [LectureColumn(heading="Light roast", points=["Origin character"]),
                           LectureColumn(heading="Dark roast", points=["Roast flavours"])]} if layout == "compare" else {"points": ["A short point"]}
    return LectureSlide(layout=layout, title=values.pop("title", "A teachable point"), unit_ids=list(ids), **(content | values))


def plan(*slides, questions=()):
    return LecturePlan(title="Rang cà phê", objectives=["Explain heat.", "Compare roasts."], takeaways=["Heat matters.", "Origin matters."],
                       questions=list(questions), parts=[LecturePart(chapter_id="overview", slides=list(slides))])


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
    assert saved.parts and saved.questions

    calls = len(provider.calls)
    Pipeline(provider).run(source, {"language": "en", "output_format": "lecture"}, tmp_path)
    assert len(provider.calls) == calls  # saved lecture parts and frame are reused

    deck = (tmp_path / "lecture.html").read_text(encoding="utf-8")
    assert deck.count('class="slide-frame"') >= 6
    assert "Explain the source model." in deck and "What does the source explain?" in deck
    assert 'data-correct="true"' in deck and "Show answer" in deck


def test_lecture_deck_escapes_text_shows_verbatim_quotes_and_source_times(tmp_path):
    source, knowledge, _ = fixture()
    knowledge.units[1].status = "inference"
    question = LectureQuestion(question="Why stop the roast?", options=["To fix the result", "No reason"], answer=0, explanation="The process ends.", unit_ids=["u4"])
    lecture = plan(slide(title="<script>alert(1)</script>", ids=("u1",)), slide("steps", ("u4",), points=["Heat", "Observe", "Stop"]),
                   slide("compare", ("u3",)), slide("quote", ("u2",), notes="Read the quote aloud."), questions=[question])
    deck = render_lecture(source, knowledge, lecture, tmp_path / "lecture.html").read_text(encoding="utf-8")

    assert "<script>alert(1)" not in deck and "&lt;script&gt;alert(1)&lt;/script&gt;" in deck
    assert "watch?v=L_Guz73e6fw&amp;t=60s" in deck and "▶ 1:00" in deck
    assert source.snippets[1].text in deck  # the quote slide and its notes show the original words
    assert 'class="steps across"' in deck and 'class="compare"' in deck
    assert "Suy luận" in deck and "Coffee origin also matters." in deck  # status and caveats stay visible
    assert deck.count('class="slide-frame"') == 2 + 1 + 4 + 1 + 1 + 1  # title, objectives, question, slides, recap, quiz, limits
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
    with pytest.raises(ValidationError):
        LectureQuestion(question="?", options=["A", "B"], answer=2, explanation="x", unit_ids=["u1"])
    with pytest.raises(ValidationError):
        LectureQuestion(question="?", options=["Same", "same"], answer=0, explanation="x", unit_ids=["u1"])


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
