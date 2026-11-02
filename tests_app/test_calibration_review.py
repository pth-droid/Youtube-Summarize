import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from tools.calibration_review import server

VIDEO = "abcdefghijk"


def unit(unit_id, snippet_ids, child_ids=()):
    return {"id": unit_id, "title": unit_id, "summary": "s", "explanation": "e", "kind": "concept", "status": "supported",
            "technical_terms": [], "child_ids": list(child_ids), "evidence": [{"snippet_ids": snippet_ids}]}


@pytest.fixture()
def run(tmp_path):
    folder = tmp_path / VIDEO
    folder.mkdir()
    snippets = [{"id": f"s{i}", "text": f"line {i}", "start": float(i)} for i in range(6)]
    (folder / "source.json").write_text(json.dumps({"title": "Sample", "video_id": VIDEO, "snippets": snippets}), encoding="utf-8")
    knowledge = {"units": [unit("idea", ["s0", "s1"], ["leaf"]), unit("leaf", ["s1"])],
                 "sections": [{"id": "sec", "title": "Intro", "snippet_ids": ["s0", "s1", "s2"], "role": "substantive", "depth": "basic"}],
                 "chapters": [{"id": "ch", "title": "One", "detail": "standard", "depth": "basic", "substantive_share": 1.0, "unit_ids": ["idea"]}]}
    (folder / "knowledge.json").write_text(json.dumps(knowledge), encoding="utf-8")
    metrics = {"source_minutes": 12, "chapters": 1, "chapter_key_ideas": 1, "leaf_units": 1}
    (folder / "calibration-summary.json").write_text(json.dumps({"title": "Sample", "display_metrics": metrics}), encoding="utf-8")
    return tmp_path


def test_lists_videos_and_marks_review_state(run):
    assert server.videos(run) == [{"id": VIDEO, "title": "Sample", "minutes": 12, "chapters": 1, "key_ideas": 1, "leaves": 1, "reviewed": False}]
    (run / VIDEO / "review-marks.json").write_text("{}", encoding="utf-8")
    assert server.videos(run)[0]["reviewed"] is True


def test_video_view_maps_evidence_to_snippet_positions(run):
    data = server.video(run, VIDEO)
    idea = data["chapters"][0]["ideas"][0]
    assert idea["evidence"] == [[0, 1]]
    assert idea["leaves"][0]["evidence"] == [[1]]
    assert (data["sections"][0]["first"], data["sections"][0]["last"]) == (0, 2)


def test_clean_marks_keeps_only_valid_values():
    marks = server.clean_marks({
        "verdict": {"coverage": "enough", "wanted": "nonsense", "note": "n"},
        "missed": [{"first": 1, "last": 3, "note": "x"}, {"first": 4, "last": 9}, {"first": 3, "last": 1}],
        "ideas": {"idea": "good", "leaf": "bad-value", "unknown": "wrong"}}, total=6, unit_ids={"idea", "leaf"})
    assert marks["verdict"] == {"coverage": "enough", "wanted": None, "note": "n"}
    assert [(m["first"], m["last"]) for m in marks["missed"]] == [(1, 3)]
    assert marks["ideas"] == {"idea": "good"}


def post(base, body, headers):
    request = urllib.request.Request(f"{base}/api/marks/{VIDEO}", json.dumps(body).encode(), headers, method="POST")
    return urllib.request.urlopen(request)


def test_marks_endpoint_requires_the_review_header_and_saves(run):
    server.Handler.run = run
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        with pytest.raises(urllib.error.HTTPError) as refused:
            post(base, {"ideas": {"idea": "good"}}, {"Content-Type": "application/json"})
        assert refused.value.code == 403
        assert not (run / VIDEO / "review-marks.json").exists()
        with post(base, {"ideas": {"idea": "good"}}, {"Content-Type": "application/json", "X-Review": "1"}) as saved:
            assert "saved" in json.load(saved)
        assert json.loads((run / VIDEO / "review-marks.json").read_text(encoding="utf-8"))["ideas"] == {"idea": "good"}
    finally:
        httpd.shutdown()
        httpd.server_close()
