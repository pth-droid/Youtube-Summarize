"""YouTube downloading: captions in the spoken language, a free yt-dlp route, readable errors and updates.

No network: yt-dlp, YouTube and PyPI are replaced by authored answers.
"""
import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from distill import audio, downloader, ingest
from distill.app import create_app
from distill.providers import ProviderError

VIDEO = "0qqW3vxOC-g"


def track(code, generated, text="Words"):
    return SimpleNamespace(language=code, language_code=code, is_generated=generated,
                           fetch=lambda: [SimpleNamespace(text=f"{text} {code}", start=1, duration=2)])


@pytest.fixture
def captions(monkeypatch):
    """Serve a caption listing; return the list of yt-dlp description requests made."""
    from youtube_transcript_api import YouTubeTranscriptApi
    asked = []
    def serve(listing, info=None):
        monkeypatch.setattr(YouTubeTranscriptApi, "list", lambda self, vid: listing)
        def describe(video_id, timeout=90):
            asked.append(video_id)
            if isinstance(info, Exception):
                raise info
            return info or {}
        monkeypatch.setattr(downloader, "video_info", describe)
        monkeypatch.setattr(ingest._TimeoutSession, "get", lambda *a, **k: SimpleNamespace(ok=False))
    serve.asked = asked
    return serve


def test_captions_follow_the_spoken_language_not_a_translation(captions):
    # A Spanish video with English subtitles uploaded as a translation: the Spanish speech wins.
    captions([track("en", False), track("es", True)], {"language": "es"})
    source = ingest.fetch_youtube(VIDEO)
    assert source.language == "es" and source.origin == "generated_captions"
    assert source.metadata["original_language"] == "es" and source.metadata["language_selection"] == "original"
    assert source.metadata["language_note"] == ""

    # Uploaded subtitles in the spoken language come before its automatic captions.
    captions([track("ar", True), track("en", True), track("en", False)], {"language": "en-US"})
    assert ingest.fetch_youtube(VIDEO).origin == "manual_captions"


def test_single_language_needs_no_lookup_and_unknown_language_is_said(captions):
    captions([track("vi", True)], {"language": "en"})
    assert ingest.fetch_youtube(VIDEO).language == "vi"
    assert captions.asked == []  # one language: nothing to choose, no extra request

    captions([track("en", False), track("es", True)], {"language": "ja"})
    source = ingest.fetch_youtube(VIDEO)
    assert source.language == "en" and "may be a translation" in source.metadata["language_note"]

    captions([track("en", False), track("es", True)], downloader.DownloadError("blocked", "Bot check"))
    source = ingest.fetch_youtube(VIDEO)
    assert source.metadata["language_selection"] == "automatic" and "could not verify" in source.metadata["language_note"]


def json3_response(events):
    return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"events": events})


INFO = {"language": "es", "title": "Probando comida", "channel": "Luisito", "thumbnail": "https://i.ytimg.com/x.jpg",
        "subtitles": {"es": [{"ext": "vtt", "url": "https://example.test/es.vtt"}, {"ext": "json3", "url": "https://example.test/es.json3", "name": "Spanish"}],
                      "en": [{"ext": "json3", "url": "https://example.test/en.json3", "name": "English"}]},
        "automatic_captions": {"es-orig": [{"ext": "json3", "url": "https://example.test/es-orig.json3", "name": "Spanish (Original)"}],
                               "fr": [{"ext": "json3", "url": "https://example.test/fr.json3", "name": "French"}]}}


def test_a_blocked_caption_request_takes_the_free_yt_dlp_route(monkeypatch, captions):
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import RequestBlocked
    captions([], INFO)
    def blocked(self, video_id):
        raise RequestBlocked(video_id)
    monkeypatch.setattr(YouTubeTranscriptApi, "list", blocked)
    fetched = []
    def get(self, url, **kwargs):
        fetched.append(url)
        return json3_response([{"tStartMs": 1200, "dDurationMs": 2500, "segs": [{"utf8": "El chef "}, {"utf8": "Rodolfo"}]},
                               {"tStartMs": 3700, "aAppend": 1, "segs": [{"utf8": "\n"}]}])
    monkeypatch.setattr(ingest._TimeoutSession, "get", get)
    source = ingest.fetch_youtube(VIDEO)
    assert fetched == ["https://example.test/es.json3"]  # uploaded Spanish subtitles, not the English translation
    assert source.metadata["caption_route"] == "yt-dlp" and source.language == "es" and source.origin == "manual_captions"
    assert [(s.text, s.start, s.end) for s in source.snippets] == [("El chef Rodolfo", 1.2, 3.7)]
    assert source.title == "Probando comida" and source.metadata["author"] == "Luisito"
    assert {"code": "es", "name": "Spanish (Original)", "generated": True} in source.metadata["available_languages"]
    assert not any(item["code"] == "fr" for item in source.metadata["available_languages"])  # translations are not offered


def test_when_both_routes_fail_the_first_reason_stays_with_the_second_route_details(monkeypatch, captions):
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import RequestBlocked
    failure = downloader.DownloadError("blocked", "YouTube asked to confirm that this is not a bot.",
                                       {"tool": "yt-dlp", "error_lines": ["ERROR: Sign in to confirm you're not a bot"]})
    captions([], failure)
    monkeypatch.setattr(YouTubeTranscriptApi, "list", lambda self, vid: (_ for _ in ()).throw(RequestBlocked(vid)))
    with pytest.raises(ingest.CaptionError) as problem:
        ingest.fetch_youtube(VIDEO)
    assert problem.value.code == "blocked" and "second attempt through yt-dlp also failed" in str(problem.value)
    assert problem.value.diagnostics["second_route"] == "blocked" and problem.value.diagnostics["error_lines"]

    captions([], {"language": "es", "subtitles": {}, "automatic_captions": {}})
    monkeypatch.setattr(YouTubeTranscriptApi, "list", lambda self, vid: (_ for _ in ()).throw(RequestBlocked(vid)))
    with pytest.raises(ingest.CaptionError) as problem:
        ingest.fetch_youtube(VIDEO)
    assert problem.value.code == "missing_captions"  # yt-dlp read the video: it truly has no captions


def test_caption_track_order_and_json3_text():
    assert downloader.caption_track(INFO, None)[:2] == ("es", "manual")
    dubbed = {"language": "fr-FR", "subtitles": {}, "automatic_captions": {
        "en-orig": [{"ext": "json3", "url": "u1"}], "fr-FR-orig": [{"ext": "json3", "url": "u2"}], "fr": [{"ext": "json3", "url": "u3"}]}}
    assert downloader.caption_track(dubbed, None)[:2] == ("fr-FR-orig", "generated")
    assert downloader.caption_track(dubbed, "en")[0] == "en-orig"
    assert downloader.caption_track({"language": None, "subtitles": {}, "automatic_captions": {}}, None) is None
    assert downloader.json3_snippets({"events": [{"tStartMs": 0, "segs": [{"utf8": "  Hello\nthere "}]}, {"segs": []}]})[0]["text"] == "Hello there"


@pytest.mark.parametrize("stderr,code", [
    ("ERROR: [youtube] abc: Sign in to confirm you’re not a bot. Use --cookies-from-browser", "blocked"),
    ("ERROR: [youtube] abc: Sign in to confirm your age.", "inaccessible"),
    ("ERROR: [youtube] abc: Private video. Sign in if you've been granted access", "inaccessible"),
    ("ERROR: unable to download video data: HTTP Error 403: Forbidden", "downloader_outdated"),
    ("WARNING: n challenge solving failed\nERROR: Requested format is not available", "downloader_outdated"),
    ("ERROR: Unable to download webpage: <urlopen error [Errno 11001] getaddrinfo failed>", "temporary"),
])
def test_yt_dlp_errors_are_named(stderr, code):
    assert downloader.classify(stderr)[0] == code


def test_error_lines_keep_the_cause_without_tokens():
    lines = downloader.error_lines("[debug] noise\nWARNING: retrying https://rr1.googlevideo.com/videoplayback?sig=SECRET&ip=1\nERROR: HTTP Error 403\n")
    assert lines == ["WARNING: retrying https://rr1.googlevideo.com/videoplayback?…", "ERROR: HTTP Error 403"]
    assert downloader.classify("Something new and unknown") is None


def test_audio_download_failure_keeps_the_tools_own_lines(tmp_path):
    command = [sys.executable, "-c", "import sys; sys.stderr.write('ERROR: [youtube] x: Sign in to confirm you are not a bot\\n'); sys.exit(1)"]
    with pytest.raises(ProviderError) as problem:
        audio._run(command)
    assert problem.value.code == "blocked" and "not a bot" in str(problem.value)
    assert problem.value.diagnostics["exit_code"] == 1 and "not a bot" in problem.value.diagnostics["error_lines"][-1]
    with pytest.raises(ProviderError) as problem:
        audio._run([sys.executable, "-c", "import sys; sys.stderr.write('odd failure\\n'); sys.exit(2)"])
    assert problem.value.code == "audio_failed" and problem.value.diagnostics["error_lines"] == ["odd failure"]


def test_node_solves_youtube_challenges_when_deno_is_missing(monkeypatch):
    monkeypatch.setattr(downloader.shutil, "which", lambda name: "C:/node/node.exe" if name == "node" else None)
    assert downloader.command("-J")[-3:] == ["--js-runtimes", "node:C:/node/node.exe", "-J"]
    monkeypatch.setattr(downloader.shutil, "which", lambda name: f"C:/bin/{name}.exe")
    assert "--js-runtimes" not in downloader.command("-J")  # yt-dlp uses Deno by default


def test_settings_report_and_update_yt_dlp(tmp_path, monkeypatch):
    app = create_app(tmp_path)
    store = app.state.store
    monkeypatch.setattr(downloader, "installed_version", lambda: "2026.8.19")
    monkeypatch.setattr(downloader, "latest_version", lambda timeout=10: "2026.10.26")
    with TestClient(app, base_url="http://127.0.0.1") as client:
        headers = {"x-distill": app.state.csrf_token}
        assert client.get("/api/tools/yt-dlp").json()["latest"] is None  # no PyPI request unless asked
        checked = client.get("/api/tools/yt-dlp?check=true").json()
        assert checked["installed"] == "2026.8.19" and checked["update_available"] is True
        assert client.get("/api/settings", headers=headers).json()["tools"]["yt-dlp"] is True

        job = store.create_job({"kind": "youtube", "video_id": VIDEO, "preferences": store.settings()})
        store.update_job(job["id"], state="retrieving")
        busy = client.post("/api/tools/yt-dlp/update", headers=headers)
        assert busy.status_code == 409 and "download" in busy.json()["detail"]
        store.update_job(job["id"], state="complete")

        monkeypatch.setattr(downloader, "update", lambda: {"previous": "2026.8.19", "installed": "2026.10.26"})
        updated = client.post("/api/tools/yt-dlp/update", headers=headers).json()
        assert updated["previous"] == "2026.8.19" and updated["installed"] == "2026.10.26"

        def broken():
            raise downloader.DownloadError("update_failed", "yt-dlp could not be updated.", {"error_lines": ["ERROR: No matching distribution"]})
        monkeypatch.setattr(downloader, "update", broken)
        failed = client.post("/api/tools/yt-dlp/update", headers=headers)
        assert failed.status_code == 502 and failed.json()["detail"] == "yt-dlp could not be updated. ERROR: No matching distribution"


def test_update_installs_default_extras_into_the_apps_environment(monkeypatch):
    calls = []
    versions = iter(["2026.8.19", "2026.10.26"])
    monkeypatch.setattr(downloader, "installed_version", lambda: next(versions))
    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(downloader.subprocess, "run", run)
    assert downloader.update() == {"previous": "2026.8.19", "installed": "2026.10.26"}
    assert calls[0][:4] == [sys.executable, "-m", "pip", "install"] and calls[0][-1] == "yt-dlp[default]"
