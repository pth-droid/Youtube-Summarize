"""Provider contracts and audio recovery checks; no remote AI/audio requests."""
import io
import json
import math
import sys
import time
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

from distill import audio, ingest, providers
from distill.models import Extraction, FigureSet, Transcript


VIDEO = "0qqW3vxOC-g"


@pytest.mark.parametrize("versioned", [False, True])
def test_import_recovery_rejects_other_video_identity(versioned):
    other = "lNWhbbAM59Y"
    body = {"video_id": other, "snippets": [{"id": "s1", "text": "Source evidence", "start": 1, "duration": 2}]}
    if versioned:
        body.update(source_id=other, title="Different video", language="en", origin="import")
    with pytest.raises(ingest.CaptionError) as problem:
        ingest.parse_import(json.dumps(body), "source.json", {"video_id": VIDEO})
    assert problem.value.code == "invalid_import"


def test_versioned_import_can_attach_known_source_video():
    body = {"source_id": "unlinked", "title": "Imported", "language": "en", "origin": "import",
            "snippets": [{"id": "s1", "text": "Source evidence"}]}
    transcript = ingest.parse_import(json.dumps(body), "source.json", {"video_id": VIDEO})
    assert transcript.video_id == transcript.source_id == VIDEO
    assert transcript.url == f"https://www.youtube.com/watch?v={VIDEO}"


def approval(**values):
    return {"approved": True, "job_id": "job-1", "source": VIDEO,
            "provider": "groq", "model": "whisper-large-v3-turbo",
            "free_only": True, "free_account_confirmed": True, **values}


def response(body=None, status=200, headers=None):
    return SimpleNamespace(status_code=status, ok=status < 400,
                           headers=headers or {}, json=lambda: body)


@pytest.mark.parametrize("value", [VIDEO, f"https://youtu.be/{VIDEO}?t=15",
    f"www.youtube.com/watch?v={VIDEO}", f"https://youtube.com/shorts/{VIDEO}",
    f"https://m.youtube.com/embed/{VIDEO}", f"https://youtube.com/live/{VIDEO}"])
def test_supported_youtube_links(value):
    assert ingest.parse_youtube_id(value) == VIDEO


@pytest.mark.parametrize("value", ["https://youtube.com.evil/watch?v=" + VIDEO,
    "https://user:pass@youtube.com/watch?v=" + VIDEO,
    "https://youtube.com:garbage/watch?v=" + VIDEO, "file:///" + VIDEO,
    "https://[invalid/watch?v=" + VIDEO, "https://youtube.com/watch?list=test", None])
def test_invalid_links_are_safe_errors(value):
    with pytest.raises(ingest.CaptionError, match="YouTube"):
        ingest.parse_youtube_id(value)


def test_subtitle_import_preserves_speaker_and_overlapping_times():
    text = "WEBVTT\n\nNOTE this --> is not a cue\nignore\n\n1\n00:00:01.250 --> 00:00:03.000 align:start\n<v Alice>Xin chào &amp; AI</v>\n\n2\n00:00:02.800 --> 00:00:04.000\nTechnical terms\n"
    source = ingest.parse_import(text.encode("utf-8"), "source.vtt", {"video_id": VIDEO})
    assert source.snippets[0].speaker == "Alice"
    assert source.snippets[0].text == "Xin chào & AI"
    assert source.snippets[1].start == 2.8
    assert source.url.endswith(VIDEO)


def test_srt_and_untimed_text_import():
    source = ingest.parse_import("1\n01:02:03,450 --> 01:02:05,000\nFirst line\nsecond line\n", "one.srt")
    assert source.snippets[0].start == 3723.45
    assert source.snippets[0].text == "First line second line"
    text = ingest.parse_import(b"\xef\xbb\xbfA concept\n\nAnother concept", "two.txt")
    assert len(text.snippets) == 2
    assert text.snippets[0].start is None
    assert text.snippets[0].timing_basis == "unknown"


def test_json_import_roundtrip_preserves_hash_and_canonical_video_url():
    source = ingest.parse_import(json.dumps([{"text": "Evidence", "start": 4, "duration": 2}]), "one.json", {"video_id": VIDEO})
    exported = source.model_dump()
    exported["url"] = "javascript:alert(1)"
    restored = ingest.parse_import(json.dumps(exported), "saved.json")
    assert restored.content_hash == source.content_hash
    assert restored.url == f"https://www.youtube.com/watch?v={VIDEO}"
    assert restored.snippets[0].end == 6


@pytest.mark.parametrize("data,name", [(b"\xff", "one.txt"), ("", "one.txt"),
    ("[]", "one.json"), ('[{"text":"Bad", "start":Infinity}]', "one.json"),
    ('[{"text":"Bad", "start":5, "end":2}]', "one.json"),
    ('[{"text":"A","id":"same"},{"text":"B","id":"same"}]', "one.json"),
    ("00:00:61 --> 00:01:05\nBad\n", "one.vtt"), ("text", "one.exe")])
def test_invalid_imports_are_rejected(data, name):
    with pytest.raises(ingest.CaptionError):
        ingest.parse_import(data, name)


def test_caption_selection_and_display_time(monkeypatch):
    from youtube_transcript_api import YouTubeTranscriptApi
    tracks = [SimpleNamespace(language="English", language_code="en", is_generated=False,
        fetch=lambda: [SimpleNamespace(text="Original", start=1, duration=3)]),
        SimpleNamespace(language="Tiếng Việt", language_code="vi", is_generated=True,
        fetch=lambda: [SimpleNamespace(text="Nguồn gốc", start=2, duration=4)])]
    monkeypatch.setattr(YouTubeTranscriptApi, "list", lambda self, vid: tracks)
    monkeypatch.setattr(ingest._TimeoutSession, "get", lambda *a, **k: response(status=404))
    source = ingest.fetch_youtube(VIDEO, "vi")
    assert source.language == "vi" and source.snippets[0].end == 6
    assert source.snippets[0].timing_basis == "caption"
    assert source.origin == "generated_captions"
    with pytest.raises(ingest.CaptionError) as problem:
        ingest.fetch_youtube(VIDEO, "de")
    assert problem.value.code == "language_mismatch" and len(problem.value.languages) == 2


def test_blocked_captions_differ_from_missing(monkeypatch):
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import RequestBlocked, TranscriptsDisabled
    for error, code in [(RequestBlocked(VIDEO), "blocked"), (TranscriptsDisabled(VIDEO), "missing_captions")]:
        def fail(*args):
            raise error
        monkeypatch.setattr(YouTubeTranscriptApi, "list", fail)
        with pytest.raises(ingest.CaptionError) as problem:
            ingest.fetch_youtube(VIDEO)
        assert problem.value.code == code


def test_strict_schema_keeps_model_types():
    schema = Extraction.model_json_schema()
    strict = providers._strict_schema(schema)
    assert strict["required"] == list(strict["properties"])
    assert strict["properties"]["relationships"]["type"] == "array"
    assert "anyOf" not in strict["properties"]["relationships"]
    assert "required" in strict["$defs"]["KnowledgeUnit"]
    assert schema == Extraction.model_json_schema()  # Input was not mutated.


def test_strict_schema_reads_field_names_as_fields_not_keywords():
    # FigureState has a field named "properties". Reading it as a keyword once added
    # fake "required" and "additionalProperties" fields, and Codex ran out of output tokens.
    strict = providers._strict_schema(FigureSet.model_json_schema())
    state = strict["$defs"]["FigureState"]
    assert list(state["properties"]) == state["required"] == ["phase_id", "caption", "properties", "unit_ids"]
    assert state["properties"]["properties"]["type"] == "array"
    assert strict["$defs"]["StateProperty"]["additionalProperties"] is False
    figure = strict["$defs"]["Figure"]["properties"]
    assert set(figure["type"]) >= {"enum", "type"} and figure["process"]["anyOf"][1] == {"type": "null"}
    for name, definition in strict["$defs"].items():
        if "properties" in definition:
            assert definition["required"] == list(definition["properties"]), name
            assert all(isinstance(field, dict) for field in definition["properties"].values()), name


def test_environment_and_public_errors_do_not_expose_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "private-openai")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "private-deepseek")
    monkeypatch.setenv("SERVICE_PASSWORD", "private-password")
    monkeypatch.setenv("CODEX_HOME", "account-home")
    safe = providers._safe_environment()
    assert safe["CODEX_HOME"] == "account-home"
    assert "OPENAI_API_KEY" not in safe and "SERVICE_PASSWORD" not in safe
    monkeypatch.setattr(providers.requests, "post", lambda *a, **kw: response({"error": "private-deepseek"}, 401))
    with pytest.raises(providers.ProviderError) as problem:
        providers.DeepSeekProvider(paid_enabled=True).generate("text", {}, Path("unused"))
    assert problem.value.code == "authentication" and "private" not in str(problem.value)


@pytest.mark.parametrize("flag", ["allow_paid_llm", "deepseek_paid_enabled", "paid_usage_approved"])
def test_deepseek_paid_aliases_and_cancel(flag, tmp_path):
    provider = providers.make_provider({"provider": "deepseek", flag: True}, cancelled=lambda: True)
    assert provider.paid_enabled
    with pytest.raises(providers.ProviderError) as problem:
        provider.generate("data", {}, tmp_path)
    assert problem.value.code == "cancelled"


def test_deepseek_requires_paid_approval(monkeypatch, tmp_path):
    monkeypatch.setattr(providers.requests, "post", lambda *a, **kw: pytest.fail("Unapproved paid request"))
    with pytest.raises(providers.ProviderError) as problem:
        providers.DeepSeekProvider(api_key="example").generate("data", {}, tmp_path)
    assert problem.value.code == "paid_approval"


@pytest.mark.parametrize("body", [{}, {"choices": None}, {"choices": [{"message": {"content": "[]"}}]},
    {"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]}])
def test_deepseek_bad_output_safe_errors(monkeypatch, tmp_path, body):
    monkeypatch.setattr(providers.requests, "post", lambda *a, **kw: response(body))
    with pytest.raises(providers.ProviderError) as problem:
        providers.DeepSeekProvider(api_key="example", paid_enabled=True).generate("data", {}, tmp_path)
    assert problem.value.code == "invalid_output"


def test_deepseek_output_and_usage(monkeypatch, tmp_path):
    def post(url, **kw):
        assert url == "https://api.deepseek.com/chat/completions"
        assert kw["json"]["response_format"] == {"type": "json_object"}
        assert kw["json"]["thinking"] == {"type": "disabled"}
        assert kw["json"]["reasoning_effort"] == "none"
        assert kw["json"]["max_tokens"] == 32768
        return response({"choices": [{"message": {"content": '{"answer":"yes"}'}}], "usage": {"completion_tokens": 12}})
    monkeypatch.setattr(providers.requests, "post", post)
    result = providers.DeepSeekProvider(api_key="example", paid_enabled=True).generate("data", {}, tmp_path)
    assert result.data == {"answer": "yes"} and result.usage["completion_tokens"] == 12


def test_deepseek_length_error_keeps_safe_usage_only(monkeypatch, tmp_path):
    body = {"choices": [{"finish_reason": "length", "message": {"content": "secret source text"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 32768,
                      "completion_tokens_details": {"reasoning_tokens": 32768}}}
    monkeypatch.setattr(providers.requests, "post", lambda *a, **kw: response(body))
    with pytest.raises(providers.ProviderError) as problem:
        providers.DeepSeekProvider(api_key="example", paid_enabled=True).generate("private prompt", {}, tmp_path)
    details = problem.value.diagnostics
    assert details["finish_reason"] == "length"
    assert details["usage"]["reasoning_tokens"] == 32768
    assert "private prompt" not in str(details) and "secret source text" not in str(details)


@pytest.mark.parametrize("status,code", [(401, "authentication"), (402, "budget"), (429, "quota"), (503, "temporary")])
def test_provider_error_boundaries(status, code):
    problem = providers.http_error(response(status=status, headers={"retry-after": "120"}), "Groq")
    assert problem.code == code
    if status in (429, 503):
        assert problem.retry_after == 120


def test_retry_after_date_and_invalid_limits():
    for value in ["Fri, 01 Jan 2038 00:00:00 GMT", "NaN", "-7", "garbage"]:
        problem = providers.http_error(response(status=429, headers={"retry-after": value}), "Groq")
        assert problem.retry_after > 0 and math.isfinite(problem.retry_after)


def codex_stub(tmp_path, content):
    script = tmp_path / "fake_codex.py"
    script.write_text(content, encoding="utf-8")
    return [sys.executable, str(script)]


def test_codex_structured_file_and_usage(monkeypatch, tmp_path):
    command = codex_stub(tmp_path, "import sys,json\nfrom pathlib import Path\nprompt=sys.stdin.read()\nassert 'untrusted data' in prompt\nPath(sys.argv[sys.argv.index('--output-last-message')+1]).write_text('{\"answer\":\"yes\"}', encoding='utf-8')\nprint(json.dumps({'type':'turn.completed','usage':{'output_tokens':2}}))\n")
    monkeypatch.setattr(providers, "_codex_command", lambda: command)
    result = providers.CodexProvider(timeout_seconds=5).generate("text", {"type": "object", "properties": {"answer": {"type": "string"}}}, tmp_path)
    assert result.data["answer"] == "yes" and result.usage["output_tokens"] == 2


def test_codex_timeout_including_blocked_input_pipe(monkeypatch, tmp_path):
    command = codex_stub(tmp_path, "import time\ntime.sleep(30)\n")
    monkeypatch.setattr(providers, "_codex_command", lambda: command)
    start = time.monotonic()
    with pytest.raises(providers.ProviderError) as problem:
        providers.CodexProvider(timeout_seconds=0.1).generate("x" * 500000, {}, tmp_path)
    assert problem.value.code == "timeout" and time.monotonic() - start < 8


def test_codex_explicit_low_effort_and_no_silent_model_switch(monkeypatch, tmp_path):
    script = "import sys,json\nfrom pathlib import Path\nsys.stdin.read()\nassert 'model_reasoning_effort=\"low\"' in sys.argv\nassert '--model' not in sys.argv\nPath(sys.argv[sys.argv.index('--output-last-message')+1]).write_text('{}',encoding='utf-8')\nprint(json.dumps({'type':'turn.completed','usage':{}}))\n"
    monkeypatch.setattr(providers, "_codex_command", lambda: codex_stub(tmp_path, script))
    provider = providers.CodexProvider(timeout_seconds=5)
    assert provider.reasoning_effort == "low" and provider.model == "CLI default"
    assert provider.generate("data", {}, tmp_path).data == {}


def test_codex_workspace_out_of_credits_is_reported_as_quota(monkeypatch, tmp_path):
    message = "Your workspace is out of credits. Ask your workspace owner to refill in order to continue."
    command = codex_stub(tmp_path, f"import sys,json\nsys.stdin.read()\nprint(json.dumps({{'type':'turn.failed','error':{{'message':{message!r}}}}}))\nsys.exit(1)\n")
    monkeypatch.setattr(providers, "_codex_command", lambda: command)
    with pytest.raises(providers.ProviderError) as problem:
        providers.CodexProvider(timeout_seconds=5).generate("text", {}, tmp_path)
    assert problem.value.code == "quota" and problem.value.diagnostics["failure_category"] == "quota"


def test_codex_cancel_and_quota_are_safe(monkeypatch, tmp_path):
    command = codex_stub(tmp_path, "import sys,json\nsys.stdin.read()\nprint(json.dumps({'type':'error','message':'usage limit private-key'}))\nsys.exit(1)\n")
    monkeypatch.setattr(providers, "_codex_command", lambda: command)
    with pytest.raises(providers.ProviderError) as problem:
        providers.CodexProvider(timeout_seconds=5).generate("text", {}, tmp_path)
    assert problem.value.code == "quota" and "private-key" not in str(problem.value)
    with pytest.raises(providers.ProviderError) as problem:
        providers.CodexProvider(cancelled=lambda: True).generate("text", {}, tmp_path)
    assert problem.value.code == "cancelled"


def test_audio_approval_blocks_before_any_io(monkeypatch, tmp_path):
    monkeypatch.setattr(audio, "_run", lambda *a, **k: pytest.fail("Unapproved download"))
    monkeypatch.setattr(audio.requests, "post", lambda *a, **k: pytest.fail("Unapproved upload"))
    for changed in [{"approved": False}, {"source": "different"}, {"model": "unknown"}, {"free_account_confirmed": False}]:
        with pytest.raises(providers.ProviderError):
            audio.transcribe_youtube(VIDEO, tmp_path, approval(**changed))
    audio.validate_approval(approval(free_only=False, paid_usage_approved=True), VIDEO, "whisper-large-v3-turbo")


def test_chunk_plan_preserves_silence_and_offsets():
    plan = audio.plan_chunks(143 * 60)
    assert plan[0]["offset"] == 0 and plan[1]["offset"] == 597
    assert plan[0]["core_end"] == plan[1]["core_start"] == 600
    assert plan[-1]["core_end"] == 8580
    for bad in [(10, float("nan"), 3), (float("inf"), 600, 3), (20, 4, 3)]:
        with pytest.raises(ValueError):
            audio.plan_chunks(*bad)


def test_boundary_dedup_retains_later_repeated_speech():
    chunks = [audio.AudioChunk(**item, path="unused") for item in audio.plan_chunks(1200)]
    rows = [{"segments": [{"start": 595, "end": 603, "text": "Repeated words"}]},
            {"segments": [{"start": 0, "end": 6, "text": "Repeated words"},
                          {"start": 20, "end": 22, "text": "Repeated words"}]}]
    snippets, warnings = audio.merge_chunks(chunks, rows)
    assert [s["start"] for s in snippets] == [595, 617]
    assert [s["id"] for s in snippets] == ["s000001", "s000002"]
    assert all("_chunk" not in s for s in snippets)


def test_same_chunk_repeats_and_partial_boundary_warning():
    chunks = [audio.AudioChunk(**item, path="unused") for item in audio.plan_chunks(1200)]
    rows = [{"segments": [{"start": 595, "end": 603, "text": "The idea needs more evidence"},
                          {"start": 596, "end": 602, "text": "The idea needs more evidence"}]},
            {"segments": [{"start": 0, "end": 10, "text": "more evidence is required today"}]}]
    snippets, warnings = audio.merge_chunks(chunks, rows)
    assert len(snippets) == 3 and snippets[-1]["text"] == "is required today"
    assert any("approximate" in warning for warning in warnings)


def test_empty_and_invalid_audio_segments():
    chunk = audio.AudioChunk(0, "unused", 0, 10, 0, 10)
    for body in [{"segments": []}, {"segments": [{"text": "Hi", "start": 2, "end": 99}]}, {"segments": [None]}]:
        with pytest.raises(providers.ProviderError):
            audio.merge_chunks([chunk], [body])


def setup_fake_audio(monkeypatch, tmp_path, duration=1200):
    source = tmp_path / "original.wav"
    source.write_bytes(b"local audio input")
    chunks = []
    for item in audio.plan_chunks(duration):
        path = tmp_path / f"section-{item['index']}.wav"
        path.write_bytes(b"synthetic test section")
        chunks.append(audio.AudioChunk(**item, path=str(path)))
    monkeypatch.setattr(audio, "prepare_chunks", lambda *a, **k: chunks)
    monkeypatch.setattr(providers.SecretStore, "get", lambda self, name: "test-key")
    return source, chunks


def test_groq_quota_resume_saves_completed_sections(monkeypatch, tmp_path):
    source, chunks = setup_fake_audio(monkeypatch, tmp_path)
    calls = []
    def post(*args, **kwargs):
        calls.append(kwargs["files"]["file"][0])
        if len(calls) == 2:
            return response(status=429, headers={"retry-after": "120"})
        return response({"language": "english", "segments": [{"text": "Original evidence", "start": 5, "end": 8}]})
    monkeypatch.setattr(audio.requests, "post", post)
    work = tmp_path / "job"
    with pytest.raises(providers.ProviderError) as problem:
        audio.transcribe_audio(source, work, approval(retain_audio=True), VIDEO)
    assert problem.value.code == "quota" and problem.value.retry_after == 120
    assert (work / "responses" / "chunk-00000.json").is_file()
    transcript = audio.transcribe_audio(source, work, approval(retain_audio=True), VIDEO)
    assert len(calls) == 3 and transcript.snippets[1].start == 602
    assert source.exists()  # User input is never deleted.
    assert "test-key" not in (work / "transcript.json").read_text(encoding="utf-8")


def test_groq_invalid_output_is_not_cached(monkeypatch, tmp_path):
    source, _ = setup_fake_audio(monkeypatch, tmp_path, 10)
    monkeypatch.setattr(audio.requests, "post", lambda *a, **k: response({"segments": [{"text": "bad", "start": 1, "end": 200}]}))
    work = tmp_path / "job"
    with pytest.raises(providers.ProviderError) as problem:
        audio.transcribe_audio(source, work, approval(), VIDEO)
    assert problem.value.code == "invalid_output"
    assert not (work / "responses" / "chunk-00000.json").exists()


@pytest.mark.parametrize("error,code", [(requests.ReadTimeout, "uncertain_timeout"),
    (requests.ConnectionError, "uncertain_request"), (requests.ConnectTimeout, "temporary")])
def test_audio_transport_retry_boundaries(monkeypatch, tmp_path, error, code):
    source, _ = setup_fake_audio(monkeypatch, tmp_path, 10)
    def fail(*a, **k):
        raise error("private-key")
    monkeypatch.setattr(audio.requests, "post", fail)
    with pytest.raises(providers.ProviderError) as problem:
        audio.transcribe_audio(source, tmp_path / "job", approval(), VIDEO)
    assert problem.value.code == code
    assert problem.value.retry_after == (30 if code == "temporary" else None)
    assert "private-key" not in str(problem.value)


@pytest.mark.parametrize("error,code", [(requests.ReadTimeout, "uncertain_timeout"),
    (requests.ConnectionError, "uncertain_request"), (requests.ConnectTimeout, "temporary")])
def test_deepseek_transport_retry_boundaries(monkeypatch, tmp_path, error, code):
    def fail(*a, **k):
        raise error("private-key")
    monkeypatch.setattr(providers.requests, "post", fail)
    with pytest.raises(providers.ProviderError) as problem:
        providers.DeepSeekProvider(api_key="example", paid_enabled=True).generate("data", {}, tmp_path)
    assert problem.value.code == code
    assert problem.value.retry_after == (30 if code == "temporary" else None)
    assert "private-key" not in str(problem.value)


def test_audio_cancel_after_sent_request_stops_remaining_calls(monkeypatch, tmp_path):
    source, _ = setup_fake_audio(monkeypatch, tmp_path)
    state = {"cancelled": False, "calls": 0}
    def post(*a, **k):
        state["calls"] += 1
        state["cancelled"] = True
        return response({"segments": [{"text": "Hi", "start": 1, "end": 2}]})
    monkeypatch.setattr(audio.requests, "post", post)
    with pytest.raises(providers.ProviderError) as problem:
        audio.transcribe_audio(source, tmp_path / "job", approval(), VIDEO, cancelled=lambda: state["cancelled"])
    assert problem.value.code == "cancelled" and state["calls"] == 1


def test_manifest_prevents_reusing_other_language(monkeypatch, tmp_path):
    source, _ = setup_fake_audio(monkeypatch, tmp_path, 10)
    monkeypatch.setattr(audio.requests, "post", lambda *a, **k: response({"segments": [{"text": "Hi", "start": 1, "end": 2}]}))
    audio.transcribe_audio(source, tmp_path / "job", approval(retain_audio=True), VIDEO, language="en")
    with pytest.raises(providers.ProviderError) as problem:
        audio.transcribe_audio(source, tmp_path / "job", approval(), VIDEO, language="vi")
    assert problem.value.code == "checkpoint_mismatch"


def test_local_ffmpeg_preparation(monkeypatch, tmp_path):
    if not audio.shutil.which("ffmpeg") or not audio.shutil.which("ffprobe"):
        pytest.skip("FFmpeg is not installed")
    path = tmp_path / "local-generated.wav"
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(44100)
        stream.writeframes(b"\0\0\0\0" * 44100)
    chunks = audio.prepare_chunks(path, tmp_path / "job")
    assert len(chunks) == 1 and chunks[0].duration == 1
    with wave.open(chunks[0].path, "rb") as stream:
        assert stream.getnchannels() == 1 and stream.getframerate() == 16000
    assert Path(chunks[0].path).stat().st_size < audio.MAX_UPLOAD_BYTES


def soniox_approval(**values):
    return approval(**({"provider": "soniox", "model": "stt-async-v5", "free_only": False, "paid_usage_approved": True} | values))


MEETING_TOKENS = [
    {"text": "Xin", "start_ms": 0, "end_ms": 300, "speaker": "1", "language": "vi", "confidence": 0.98},
    {"text": " chào", "start_ms": 300, "end_ms": 600, "speaker": "1", "language": "vi", "confidence": 0.97},
    {"text": " cả nhà.", "start_ms": 600, "end_ms": 1100, "speaker": "1", "language": "vi", "confidence": 0.96},
    {"text": " Chào", "start_ms": 1500, "end_ms": 1800, "speaker": "2", "language": "vi", "confidence": 0.99},
    {"text": " anh.", "start_ms": 1800, "end_ms": 2100, "speaker": "2", "language": "vi", "confidence": 0.99},
    {"text": " Bắt", "start_ms": 5000, "end_ms": 5300, "speaker": "2", "language": "vi", "confidence": 0.4},
    {"text": " đầu", "start_ms": 5300, "end_ms": 5600, "speaker": "2", "language": "vi", "confidence": 0.5},
    {"text": " nhé", "start_ms": 5600, "end_ms": 5900, "speaker": "1", "language": "vi", "confidence": 0.9},
]


def test_soniox_tokens_become_speaker_turns():
    snippets, warnings, count = audio.soniox_snippets(MEETING_TOKENS)
    assert [(s["speaker"], s["text"]) for s in snippets] == [
        ("Speaker 1", "Xin chào cả nhà."), ("Speaker 2", "Chào anh."), ("Speaker 2", "Bắt đầu"), ("Speaker 1", "nhé")]
    assert count == 2 and snippets[2]["start"] == 5 and snippets[0]["end"] == 1.1
    assert [s["id"] for s in snippets] == ["s000001", "s000002", "s000003", "s000004"]
    assert warnings == ["Uncertain transcription near 5.0s; compare with original audio."]
    Transcript(source_id="import:x", snippets=snippets)


def test_soniox_single_voice_has_no_label_and_numbering_follows_first_voice():
    lecture = [{"text": "One", "start_ms": 0, "end_ms": 400, "speaker": "1"},
               {"text": " Uno", "start_ms": 400, "end_ms": 800, "speaker": "1", "translation_status": "translation"},
               {"text": " voice.", "start_ms": 400, "end_ms": 900, "speaker": "1"}]
    snippets, _, count = audio.soniox_snippets(lecture)
    assert count == 1 and snippets == [{"id": "s000001", "text": "One voice.", "start": 0, "end": 0.9, "duration": 0.9, "timing_basis": "speech", "speaker": None}]
    swapped = audio.soniox_snippets([{"text": "Hi", "start_ms": 0, "end_ms": 1, "speaker": "3"}, {"text": " Hey", "start_ms": 2, "end_ms": 3, "speaker": "1"}])[0]
    assert [s["speaker"] for s in swapped] == ["Speaker 1", "Speaker 2"]
    for tokens in [[{"text": "x", "end_ms": 1}], [{"text": "x", "start_ms": 5, "end_ms": 1}], [None], [{"start_ms": 0, "end_ms": 1}]]:
        with pytest.raises(providers.ProviderError) as problem:
            audio.soniox_snippets(tokens)
        assert problem.value.code == "invalid_output"
    with pytest.raises(providers.ProviderError) as problem:
        audio.soniox_snippets([])
    assert problem.value.code == "audio_failed"


def test_soniox_is_the_default_and_requires_paid_consent(monkeypatch, tmp_path):
    request = audio.approval_request({}, "job-1", VIDEO, "Captions unavailable")
    assert request["provider"] == "soniox" and request["model"] == "stt-async-v5"
    assert request["free_only"] is False and request["speaker_labels"] and not request["approved"]
    groq = audio.approval_request({"transcription_providers": {"video": "groq"}, "groq_free_only": True}, "job-1", VIDEO, "reason", languages=["vi"])
    assert groq["provider"] == "groq" and groq["free_only"] and groq["languages"] == ["vi"] and "speaker_labels" not in groq
    # Each workflow has its own service; an unknown or missing choice stays on Soniox.
    meeting_on_groq = {"transcription_providers": {"meeting": "groq", "lecture": "elsewhere"}}
    assert audio.approval_request(meeting_on_groq, "job-1", VIDEO, "reason", workflow="meeting")["provider"] == "groq"
    assert audio.approval_request(meeting_on_groq, "job-1", VIDEO, "reason", workflow="lecture")["provider"] == "soniox"
    assert audio.approval_request(meeting_on_groq, "job-1", VIDEO, "reason")["workflow"] == "video"
    monkeypatch.setattr(audio.requests, "request", lambda *a, **k: pytest.fail("Unapproved upload"))
    monkeypatch.setattr(audio, "_run", lambda *a, **k: pytest.fail("Unapproved download"))
    for changed in [{"paid_usage_approved": False}, {"model": "whisper-large-v3"}, {"provider": "other"}, {"approved": False}]:
        with pytest.raises(providers.ProviderError):
            audio.transcribe_youtube(VIDEO, tmp_path, soniox_approval(**changed))
    audio.validate_approval(soniox_approval(), VIDEO, "stt-async-v5")


def setup_soniox(monkeypatch, tmp_path, routes):
    source = tmp_path / "meeting.m4a"
    source.write_bytes(b"local meeting audio")
    def prepare(audio_path, work_dir, cancelled=None):
        path = work_dir / "chunks" / "upload.flac"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"synthetic flac")
        return path, 1800.0
    calls = []
    def request(method, url, **kwargs):
        path = url.removeprefix(audio.SONIOX_API)
        calls.append((method, path, kwargs.get("json")))
        result = routes(method, path)
        if isinstance(result, Exception):
            raise result
        return result
    monkeypatch.setattr(audio, "prepare_upload", prepare)
    monkeypatch.setattr(audio, "SONIOX_POLL_SECONDS", 0)
    monkeypatch.setattr(providers.SecretStore, "get", lambda self, name: "test-key" if name == "soniox" else None)
    monkeypatch.setattr(audio.requests, "request", request)
    return source, calls


def test_soniox_resumes_the_saved_request_without_a_second_upload_or_charge(monkeypatch, tmp_path):
    phase = {"done": False}
    def routes(method, path):
        if (method, path) == ("POST", "/files"): return response({"id": "file-1"})
        if (method, path) == ("POST", "/transcriptions"): return response({"id": "tr-1", "status": "queued"})
        if (method, path) == ("GET", "/transcriptions/tr-1"):
            return response({"status": "completed"}) if phase["done"] else response(status=429, headers={"retry-after": "90"})
        if (method, path) == ("GET", "/transcriptions/tr-1/transcript"): return response({"text": "", "tokens": MEETING_TOKENS})
        if method == "DELETE": return response(status=204)
        pytest.fail(f"Unexpected Soniox call {method} {path}")
    source, calls = setup_soniox(monkeypatch, tmp_path, routes)
    work = tmp_path / "job"
    with pytest.raises(providers.ProviderError) as problem:
        audio.transcribe_audio(source, work, soniox_approval(), VIDEO, language="vi")
    assert problem.value.code == "quota" and problem.value.retry_after == 90
    assert calls[1][2] == {"model": "stt-async-v5", "file_id": "file-1", "enable_speaker_diarization": True,
                           "enable_language_identification": True, "client_reference_id": "job-1", "language_hints": ["vi"]}
    phase["done"] = True
    calls.clear()
    transcript = audio.transcribe_audio(source, work, soniox_approval(), VIDEO, language="vi")
    assert [(m, p) for m, p, _ in calls] == [("GET", "/transcriptions/tr-1"), ("GET", "/transcriptions/tr-1/transcript"),
                                             ("DELETE", "/transcriptions/tr-1"), ("DELETE", "/files/file-1")]
    assert [s.speaker for s in transcript.snippets] == ["Speaker 1", "Speaker 2", "Speaker 2", "Speaker 1"]
    assert transcript.language == "vi" and transcript.metadata["provider"] == "soniox"
    assert transcript.metadata["speaker_count"] == 2 and transcript.metadata["audio_duration"] == 1800
    assert source.exists() and not (work / "chunks" / "upload.flac").exists()
    assert "test-key" not in (work / "transcript.json").read_text(encoding="utf-8")
    calls.clear()
    assert audio.transcribe_audio(source, work, soniox_approval(), VIDEO, language="vi").snippets == transcript.snippets
    assert calls == []


def test_soniox_failed_transcription_is_resubmitted_without_reupload(monkeypatch, tmp_path):
    created = []
    def routes(method, path):
        if (method, path) == ("POST", "/files"): return response({"id": "file-1"})
        if (method, path) == ("POST", "/transcriptions"):
            created.append(path)
            return response({"id": f"tr-{len(created)}"})
        if (method, path) == ("GET", "/transcriptions/tr-1"):
            return response({"status": "error", "error_type": "invalid_audio", "error_message": "Audio could not be decoded"})
        if (method, path) == ("GET", "/transcriptions/tr-2"): return response({"status": "processing"})
        pytest.fail(f"Unexpected Soniox call {method} {path}")
    source, calls = setup_soniox(monkeypatch, tmp_path, routes)
    with pytest.raises(providers.ProviderError) as problem:
        audio.transcribe_audio(source, tmp_path / "job", soniox_approval(), VIDEO)
    assert problem.value.code == "provider_failed" and "Audio could not be decoded" in str(problem.value)
    monkeypatch.setattr(audio, "SONIOX_WAIT_SECONDS", 0)
    with pytest.raises(providers.ProviderError) as problem:
        audio.transcribe_audio(source, tmp_path / "job", soniox_approval(), VIDEO)
    assert problem.value.code == "temporary" and problem.value.retry_after == 120
    assert [p for m, p, _ in calls if m == "POST"] == ["/files", "/transcriptions", "/transcriptions"]


@pytest.mark.parametrize("failing,error,code", [
    ("POST /transcriptions", requests.ReadTimeout, "uncertain_timeout"),
    ("POST /transcriptions", requests.ConnectionError, "uncertain_request"),
    ("POST /transcriptions", requests.ConnectTimeout, "temporary"),
    ("POST /files", requests.ReadTimeout, "temporary"),
    ("GET /transcriptions/tr-1", requests.ConnectionError, "temporary")])
def test_soniox_only_the_billable_request_is_uncertain(monkeypatch, tmp_path, failing, error, code):
    def routes(method, path):
        if f"{method} {path}" == failing: return error("private-key")
        if path == "/files": return response({"id": "file-1"})
        if path == "/transcriptions": return response({"id": "tr-1"})
        pytest.fail(f"Unexpected Soniox call {method} {path}")
    source, _ = setup_soniox(monkeypatch, tmp_path, routes)
    with pytest.raises(providers.ProviderError) as problem:
        audio.transcribe_audio(source, tmp_path / "job", soniox_approval(), VIDEO)
    assert problem.value.code == code and "private-key" not in str(problem.value)
    assert problem.value.retry_after == (30 if code == "temporary" else None)


def test_soniox_duration_is_limited_to_one_upload(monkeypatch, tmp_path):
    monkeypatch.setattr(audio, "_probe_duration", lambda *a, **k: audio.SONIOX_MAX_DURATION_SECONDS + 1)
    monkeypatch.setattr(audio, "_run", lambda *a, **k: pytest.fail("Over-limit audio must not be converted"))
    with pytest.raises(providers.ProviderError) as problem:
        audio.prepare_upload(tmp_path / "long.wav", tmp_path / "job")
    assert problem.value.code == "audio_duration_limit"


def test_local_ffmpeg_soniox_upload_is_mono_16khz_flac(tmp_path):
    if not audio.shutil.which("ffmpeg") or not audio.shutil.which("ffprobe"):
        pytest.skip("FFmpeg is not installed")
    path = tmp_path / "local-generated.wav"
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(44100)
        stream.writeframes(b"\0\0\0\0" * 44100)
    upload, duration = audio.prepare_upload(path, tmp_path / "job")
    assert upload.name == "upload.flac" and duration == 1
    probe = audio._run([audio._binary("ffprobe"), "-v", "error", "-show_entries", "stream=codec_name,channels,sample_rate", "-of", "json", str(upload)])
    assert json.loads(probe)["streams"][0] == {"codec_name": "flac", "sample_rate": "16000", "channels": 1}
