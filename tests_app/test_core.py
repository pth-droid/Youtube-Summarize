"""Recovery, consent and persistence contracts without external service calls."""
import io
import json
import os
import sqlite3
import time
import zipfile
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from tests_app.learning_fixture import fixture
from tests_app.test_learning import SemanticFixtureProvider
from distill.app import create_app
from distill.config import DEFAULT_SETTINGS
from distill.ingest import CaptionError
from distill.providers import ProviderError
from distill.renderer import render_page
from distill.storage import Store
from distill.worker import Worker


def new_job(store, kind="import", **preferences):
    return store.create_job({"kind": kind, "video_id": "L_Guz73e6fw", "preferences": DEFAULT_SETTINGS | preferences})


def saved_page(store):
    source, knowledge, plan = fixture()
    job = new_job(store)
    store.checkpoint(job["id"], "source", source.model_dump(mode="json"))
    store.write_json(job["id"], "source.json", source.model_dump(mode="json"))
    path = render_page(source, knowledge, plan, store.artifact_dir(job["id"]) / "page.html")
    return store.publish_generation(job["id"], {"page_path": path, "source_id": source.source_id, "title": source.title, "summary": knowledge.main_conclusion})


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, base_url="http://127.0.0.1") as result:
        result.headers["x-distill"] = app.state.csrf_token
        result.store = app.state.store
        yield result


def test_one_worker_gate_and_expired_lease_preserve_checkpoint(tmp_path):
    store = Store(tmp_path)
    first, second = new_job(store), new_job(store)
    store.checkpoint(first["id"], "source", {"text": "saved"})
    assert store.claim_job("first")["id"] == first["id"]
    assert store.claim_job("second") is None
    store.update_job(first["id"], lease_until=time.time() - 1)
    resumed = store.claim_job("second")
    assert resumed["id"] == first["id"] and resumed["attempts"] == 2
    assert store.load_checkpoint(first["id"], "source") == {"text": "saved"}
    assert not store.heartbeat(first["id"], "first")
    with pytest.raises(InterruptedError):
        store.update_job(first["id"], expected_owner="first", state="failed")
    with pytest.raises(InterruptedError):
        store.checkpoint(first["id"], "source", {}, expected_owner="first")
    store.release(first["id"], "first")
    assert store.get_job(first["id"])["lease_owner"] == "second"
    assert store.get_job(second["id"])["state"] == "queued"


def test_cancel_queued_and_active_prevent_publication(tmp_path):
    store = Store(tmp_path)
    queued = new_job(store)
    assert store.cancel(queued["id"])["state"] == "cancelled"
    job = new_job(store)
    store.claim_job("worker")
    assert store.cancel(job["id"])["cancel_requested"]
    path = store.artifact_dir(job["id"]) / "page.html"
    store.atomic_write(path, b"<p>Unpublished</p>")
    with pytest.raises(InterruptedError):
        store.publish_generation(job["id"], {"page_path": path}, expected_owner="worker")
    assert not store.library()


def test_worker_import_completes_and_restart_reuses_source(tmp_path, monkeypatch):
    store = Store(tmp_path)
    source, _, _ = fixture()
    job = new_job(store, language="en")
    store.checkpoint(job["id"], "source", source.model_dump(mode="json"))
    provider = SemanticFixtureProvider()
    monkeypatch.setattr("distill.providers.make_provider", lambda *_args, **_kwargs: provider)
    assert Worker(store).run_once()
    complete = store.get_job(job["id"])
    assert complete["state"] == "complete"
    assert store.get_generation(complete["generation_id"])
    assert not Worker(store).run_once()


@pytest.mark.parametrize("code", ["uncertain_timeout", "uncertain_request", "paid_approval"])
def test_uncertain_or_unapproved_cloud_request_requires_manual_retry(tmp_path, code):
    store = Store(tmp_path)
    job = new_job(store)
    worker = Worker(store)
    store.claim_job(worker.owner)
    worker._handle_error(job["id"], ProviderError(code, "Request may have completed. Retry manually."))
    assert store.get_job(job["id"])["state"] == "failed"
    assert store.get_job(job["id"])["next_run_at"] == 0


def test_quota_wait_and_bounded_temporary_retries(tmp_path):
    store = Store(tmp_path)
    job = new_job(store)
    worker = Worker(store)
    store.claim_job(worker.owner)
    worker._handle_error(job["id"], ProviderError("rate_limit", "Wait", retry_after=30))
    assert store.get_job(job["id"])["state"] == "waiting_for_quota"
    for number in range(3):
        worker._handle_error(job["id"], ProviderError("temporary", "Connection unavailable"))
        assert store.get_job(job["id"])["state"] == ("failed" if number == 2 else "waiting_for_quota")


def test_caption_failure_waits_for_explicit_audio_approval(tmp_path, monkeypatch):
    store = Store(tmp_path)
    job = new_job(store, kind="youtube")
    def unavailable(*_args, **_kwargs):
        raise CaptionError("no_captions", "Captions unavailable")
    monkeypatch.setattr("distill.ingest.fetch_youtube", unavailable)
    monkeypatch.setattr("distill.audio.transcribe_youtube", lambda *_a, **_k: pytest.fail("Audio must not start"))
    Worker(store).run_once()
    waiting = store.get_job(job["id"])
    assert waiting["state"] == "awaiting_approval"
    assert not waiting["approval"]["approved"]
    assert waiting["approval"]["source"] == "L_Guz73e6fw"


def test_local_boundary_validation_and_secret_values_not_echoed(client):
    assert client.post("/api/jobs", json={"url": "https://youtu.be/L_Guz73e6fw"}, headers={"origin": "https://other.example"}).status_code == 403
    assert client.post("/api/jobs", json={"url": "https://youtu.be/L_Guz73e6fw"}, headers={"x-distill": "invalid"}).status_code == 403
    assert client.get("/api/health", headers={"host": "other.example"}).status_code == 403
    response = client.put("/api/credentials/deepseek", json={"key": "SECRET", "extra": "SECRET"})
    assert response.status_code == 422 and "SECRET" not in response.text
    assert client.post("/api/jobs", json={"url": "https://other.example/video"}).status_code == 422


def test_failed_paid_retry_does_not_destroy_checkpoint_or_preferences(client):
    job = new_job(client.store)
    client.store.update_job(job["id"], state="failed")
    client.store.checkpoint(job["id"], "extraction", {"saved": True})
    response = client.post(f"/api/jobs/{job['id']}/retry", json={"provider": "deepseek"})
    assert response.status_code == 409
    assert client.store.load_checkpoint(job["id"], "extraction") == {"saved": True}
    assert client.store.get_job(job["id"])["input"]["preferences"]["provider"] == "codex"
    response = client.post(f"/api/jobs/{job['id']}/retry", json={"provider": "deepseek", "paid_usage_approved": True})
    assert response.status_code == 200 and response.json()["input"]["preferences"]["paid_usage_approved"]
    assert client.store.load_checkpoint(job["id"], "extraction") is None


def test_settings_paid_opt_in_is_carried_to_worker_on_retry(client):
    job = new_job(client.store)
    client.store.update_job(job["id"], state="failed")
    client.store.save_settings({"allow_paid_llm": True})
    response = client.post(f"/api/jobs/{job['id']}/retry", json={"provider": "deepseek"})
    assert response.status_code == 200
    assert response.json()["input"]["preferences"]["paid_usage_approved"]


def test_import_retains_timing_and_recovery_replaces_source(client):
    srt = b"1\n00:00:10,000 --> 00:00:12,000\nSource passage.\n"
    response = client.post("/api/import", files={"file": ("source.srt", srt)}, data={"title": "Imported source"})
    assert response.status_code == 201
    job_id = response.json()["job"]["id"]
    source = client.store.load_checkpoint(job_id, "source")
    assert source["snippets"][0]["start"] == 10
    client.store.update_job(job_id, state="failed")
    client.store.checkpoint(job_id, "extraction", {"stale": True})
    result = client.post(f"/api/jobs/{job_id}/import", files={"file": ("replacement.txt", b"New source passage.")})
    assert result.status_code == 200 and result.json()["state"] == "queued"
    assert client.store.load_checkpoint(job_id, "extraction") is None
    assert client.store.load_checkpoint(job_id, "source")["snippets"][0]["start"] is None


def test_import_is_not_claimable_until_its_source_is_durable(client, monkeypatch):
    original = client.store.create_job
    def observe(*args, **kwargs):
        job = original(*args, **kwargs)
        assert client.store.claim_job("racing-worker") is None
        return job
    monkeypatch.setattr(client.store, "create_job", observe)
    response = client.post("/api/import", files={"file": ("source.txt", b"Durable before processing.")})
    assert response.status_code == 201
    job = client.store.claim_job("worker")
    assert job["id"] == response.json()["job"]["id"]
    assert client.store.load_checkpoint(job["id"], "source")


def test_audio_import_stays_local_until_approval_and_cannot_bypass_free_confirmation(client):
    client.store.save_settings({"transcription_providers": {"video": "soniox", "meeting": "groq", "lecture": "soniox"}})
    response = client.post("/api/audio-import", files={"file": ("sample.wav", b"AUTHORED TEST NOT REAL AUDIO")})
    assert response.status_code == 201
    job = response.json()["job"]
    assert job["state"] == "awaiting_approval" and job["approval"]["provider"] == "groq"
    assert job["input"]["recording_type"] == "meeting" and job["approval"]["workflow"] == "meeting"
    lecture = client.post("/api/audio-import", data={"recording_type": "lecture"}, files={"file": ("talk.wav", b"AUTHORED TEST NOT REAL AUDIO")})
    assert lecture.status_code == 201 and lecture.json()["job"]["approval"]["provider"] == "soniox"
    assert client.post("/api/audio-import", data={"recording_type": "podcast"}, files={"file": ("x.wav", b"AUDIO")}).status_code == 422
    path = f"/api/jobs/{job['id']}/approve"
    assert client.post(path, json={"approved": True}).status_code == 409
    approved = client.post(path, json={"approved": True, "free_account_confirmed": True})
    assert approved.status_code == 200 and approved.json()["approval"]["approved"]


def test_audio_import_defaults_to_soniox_speaker_labels_and_needs_paid_consent(client):
    response = client.post("/api/audio-import", files={"file": ("meeting.m4a", b"AUTHORED TEST NOT REAL AUDIO")})
    job = response.json()["job"]
    assert job["approval"]["provider"] == "soniox" and job["approval"]["speaker_labels"]
    assert "Soniox" in job["progress"]["message"]
    path = f"/api/jobs/{job['id']}/approve"
    assert client.post(path, json={"approved": True, "free_account_confirmed": True}).status_code == 409
    approved = client.post(path, json={"approved": True, "paid_usage_approved": True})
    assert approved.status_code == 200 and approved.json()["approval"]["paid_usage_approved"]
    assert client.put("/api/settings", json={"transcription_providers": {"meeting": "elsewhere"}}).status_code == 422
    assert client.put("/api/settings", json={"transcription_providers": {"podcast": "soniox"}}).status_code == 422
    assert client.put("/api/settings", json={"output_format": "poster"}).status_code == 422


def test_library_export_backup_restore_and_managed_delete(client, tmp_path):
    generation = saved_page(client.store)
    assert client.get("/api/library?q=fixture").json()["generations"][0]["id"] == generation["id"]
    page = client.get(f"/api/generations/{generation['id']}/page")
    assert page.status_code == 200 and "sandbox allow-scripts" in page.headers["content-security-policy"]
    exported = client.get(f"/api/generations/{generation['id']}/export")
    assert "attachment" in exported.headers["content-disposition"]
    backup = client.post("/api/backup")
    assert backup.status_code == 200
    restored = tmp_path / "restored"
    with zipfile.ZipFile(io.BytesIO(backup.content)) as archive:
        assert "library.sqlite3" in archive.namelist()
        assert not any("credential" in name for name in archive.namelist())
        archive.extractall(restored)
    restored_store = Store(restored)
    assert restored_store.get_generation(generation["id"])
    assert restored_store.managed_path(generation["page_path"]).read_bytes() == exported.content
    assert client.delete(f"/api/generations/{generation['id']}").status_code == 200
    assert not client.store.library()
    assert not (client.store.root / "jobs" / generation["job_id"]).exists()


def test_backup_rejects_running_jobs(client):
    new_job(client.store)
    assert client.post("/api/backup").status_code == 409


def test_generation_details_aggregate_reported_usage_without_secrets(client):
    generation = saved_page(client.store)
    path = client.store.write_json(generation["job_id"], "generation.json", {"model": "fixture-model", "usage": [{"input_tokens": 30, "output_tokens": 5}, {"prompt_tokens": 20, "completion_tokens": 7}], "secret": "MUST_NOT_LEAK"})
    with client.store.connection() as con:
        con.execute("UPDATE generations SET metadata=? WHERE id=?", (json.dumps({"generation_path": str(path)}), generation["id"]))
    response = client.get(f"/api/generations/{generation['id']}/details")
    assert response.status_code == 200 and "MUST_NOT_LEAK" not in response.text
    assert response.json()["input_tokens"] == 50
    assert response.json()["output_tokens"] == 12
    assert response.json()["subscription_allowance"] == "Unknown"
    assert "checkpoint" in response.json()["usage_scope"]


def test_managed_path_rejects_traversal(tmp_path):
    store = Store(tmp_path)
    with pytest.raises(ValueError):
        store.managed_path("../outside.html")


def test_old_failed_audio_cleanup_preserves_retained_and_source_text(tmp_path):
    store = Store(tmp_path)
    removable = new_job(store, kind="audio_import")
    retained = new_job(store, kind="audio_import", retain_audio=True)
    old = time.time() - 90000
    for job in (removable, retained):
        store.update_job(job["id"], state="failed")
        folder = store.artifact_dir(job["id"])
        store.atomic_write(folder / "imported-audio.wav", b"temporary")
        store.atomic_write(folder / "source.json", b"saved text")
        os.utime(folder / "imported-audio.wav", (old, old))
        with store.connection() as con:
            con.execute("UPDATE jobs SET updated_at=? WHERE id=?", (datetime.fromtimestamp(old, timezone.utc).isoformat(), job["id"]))
    assert store.cleanup_audio() == 1
    assert not (store.artifact_dir(removable["id"]) / "imported-audio.wav").exists()
    assert (store.artifact_dir(removable["id"]) / "source.json").exists()
    assert (store.artifact_dir(retained["id"]) / "imported-audio.wav").exists()


def test_import_language_retry_cannot_destroy_saved_transcript(client):
    job = new_job(client.store, kind="audio_import")
    client.store.update_job(job["id"], state="failed")
    client.store.checkpoint(job["id"], "source", {"preserved": True})
    result = client.post(f"/api/jobs/{job['id']}/retry", json={"source_language": "vi"})
    assert result.status_code == 409
    assert client.store.load_checkpoint(job["id"], "source") == {"preserved": True}


def test_app_lifespan_starts_and_stops_separate_worker(tmp_path):
    application = create_app(tmp_path, auto_worker=True)
    with TestClient(application, base_url="http://127.0.0.1") as client:
        process = application.state.worker_process
        assert process is not None and process.poll() is None
        assert client.get("/api/health").json()["worker"] == "running"
    assert process.poll() is not None
