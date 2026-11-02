"""Local Whisper: free transcription on this computer, approved without billing questions, timing kept."""
import json
import shutil
import subprocess

import pytest

from distill import audio
from distill.audio import approval_request, transcribe_audio, validate_approval
from distill.providers import ProviderError
from tests_app.test_core import client  # noqa: F401  (fixture)


def test_a_local_request_needs_no_key_or_billing_consent():
    request = approval_request({"transcription_providers": {"lecture": "local"}}, "job1", "import:talk", "Audio import.", workflow="lecture")
    assert request["provider"] == "local" and request["model"] == "large-v3-turbo" and request["local"] and "not uploaded" in request["quota"]
    validate_approval(request | {"approved": True}, "import:talk", "large-v3-turbo")
    with pytest.raises(ProviderError, match="local Whisper model"):
        validate_approval(request | {"approved": True, "model": "tiny.en"}, "import:talk", "tiny.en")


def test_an_audio_import_set_to_local_is_approved_with_the_source_alone(client):  # noqa: F811
    client.store.save_settings({"transcription_providers": {"video": "soniox", "meeting": "local", "lecture": "soniox"}, "local_whisper_model": "small"})
    job = client.post("/api/audio-import", files={"file": ("meeting.wav", b"AUTHORED TEST NOT REAL AUDIO")}).json()["job"]
    assert job["approval"]["provider"] == "local" and job["approval"]["model"] == "small"
    assert "on this computer" in job["progress"]["message"]
    approved = client.post(f"/api/jobs/{job['id']}/approve", json={"approved": True})
    assert approved.status_code == 200 and approved.json()["approval"]["approved"]
    assert client.put("/api/settings", json={"local_whisper_model": "tiny"}).status_code == 422
    assert "local-whisper" in client.get("/api/settings").json()["tools"]


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_local_whisper_output_becomes_a_timed_transcript_and_the_temporary_wav_goes(tmp_path, monkeypatch):
    recording = tmp_path / "talk.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=6", str(recording)], check=True)
    commands = []

    def fake_worker(command, log, duration, progress=None, cancelled=None):
        commands.append(command)
        assert command[1] == "-I" and command[2].endswith("whisper_worker.py") and command[4:6] == ["large-v3-turbo", "vi"]
        segments = [{"start": 0.4, "end": 2.5, "text": " Xin chào.", "avg_logprob": -0.2, "no_speech_prob": 0.01},
                    {"start": 3.0, "end": 5.8, "text": "Hôm nay nói về rang cà phê.", "avg_logprob": -1.4, "no_speech_prob": 0.1}]
        open(command[6], "w", encoding="utf-8").write(json.dumps({"language": "vi", "duration": duration, "segments": segments}))

    monkeypatch.setattr(audio, "whisper_python", lambda: "python-with-whisper")
    monkeypatch.setattr(audio, "_run_whisper", fake_worker)
    approval = approval_request({"transcription_providers": {"lecture": "local"}}, "job1", "import:talk", "Audio import.", workflow="lecture") | {"approved": True}
    work = tmp_path / "work"
    transcript = transcribe_audio(recording, work, approval, "import:talk", language="vi-VN")
    assert [s.text for s in transcript.snippets] == ["Xin chào.", "Hôm nay nói về rang cà phê."]
    assert transcript.snippets[1].start == 3.0 and transcript.snippets[1].timing_basis == "speech"
    assert transcript.language == "vi" and transcript.metadata["provider"] == "local" and transcript.metadata["speaker_labels"] == "none"
    assert any("Uncertain" in warning for warning in transcript.metadata["warnings"])
    assert not (work / "chunks" / "local.wav").exists() and recording.exists()
    # A second run reuses the saved transcript instead of running Whisper again.
    assert transcribe_audio(recording, work, approval, "import:talk", language="vi-VN").snippets == transcript.snippets and len(commands) == 1


def test_without_faster_whisper_the_job_says_how_to_install_it(tmp_path, monkeypatch):
    monkeypatch.setattr(audio, "whisper_python", lambda: None)
    approval = approval_request({"transcription_providers": {"video": "local"}}, "job1", "L_Guz73e6fw", "No captions.") | {"approved": True}
    with pytest.raises(ProviderError, match="reelcrew transcribe setup whisper"):
        audio.transcribe_youtube("L_Guz73e6fw", tmp_path, approval)
