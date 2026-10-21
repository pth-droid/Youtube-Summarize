"""Folder selection preserves saved evidence and prevents writes to old copies."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests_app.test_core import saved_page, new_job
from visual_learning.app import create_app
from visual_learning.config import default_data_dir
from visual_learning.storage import LibraryRelocated, Store
from visual_learning.worker import Worker


@pytest.fixture(autouse=True)
def isolated_locator(tmp_path, monkeypatch):
    monkeypatch.setenv("VISUAL_LEARNING_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.delenv("VISUAL_LEARNING_DATA_DIR", raising=False)


def test_move_keeps_pages_sources_preferences_and_remembers_restart(tmp_path):
    store = Store(tmp_path / "original")
    page = saved_page(store)
    original_html = store.managed_path(page["page_path"]).read_bytes()
    store.save_settings({"language": "en"})
    stopped = new_job(store, kind="audio_import")
    audio = store.artifact_dir(stopped["id"]) / "imported-audio.wav"
    audio.write_bytes(b"saved audio")
    store.update_job(stopped["id"], state="cancelled", input={"kind": "audio_import", "audio_path": str(audio), "preferences": {}})
    store.checkpoint(stopped["id"], "cached", {"work_dir": str(audio.parent)})
    store.write_json(stopped["id"], "generation.json", {"path": str(audio)})
    migrated = store.relocate(str(tmp_path / "selected"))
    assert migrated.library()[0]["id"] == page["id"]
    assert migrated.managed_path(page["page_path"]).read_bytes() == original_html
    assert migrated.load_checkpoint(page["job_id"], "source")
    assert migrated.settings()["language"] == "en"
    assert migrated.get_job(stopped["id"])["input"]["audio_path"] == str(migrated.root / audio.relative_to(store.root))
    assert migrated.load_checkpoint(stopped["id"], "cached")["work_dir"] == str(migrated.root / audio.parent.relative_to(store.root))
    assert json.loads((migrated.root / audio.parent.relative_to(store.root) / "generation.json").read_text())["path"].startswith(str(migrated.root))
    assert audio.read_bytes() == b"saved audio"
    assert default_data_dir() == migrated.root
    assert Store(store.root).root == migrated.root
    assert list(store.root.glob("library-before-move-*.sqlite3"))
    assert (store.root / "LIBRARY_MOVED.txt").is_file()
    with pytest.raises(LibraryRelocated):
        store.create_job({"kind": "import"})


def test_missing_selected_library_never_starts_an_empty_library(tmp_path):
    store = Store(tmp_path / "original")
    migrated = store.relocate(str(tmp_path / "selected"))
    migrated.db_path.unlink()
    with pytest.raises(ValueError, match="unavailable"):
        default_data_dir()


@pytest.mark.parametrize("state", ["queued", "analyzing", "waiting_for_quota"])
def test_busy_jobs_prevent_move_without_changing_selection(tmp_path, state):
    store = Store(tmp_path / "original")
    job = new_job(store)
    store.update_job(job["id"], state=state)
    target = tmp_path / "new"
    with pytest.raises(ValueError, match="processing"):
        store.relocate(str(target))
    assert not target.exists()
    assert store.get_job(job["id"])["state"] == state


def test_reject_existing_nested_relative_and_config_folders(tmp_path):
    store = Store(tmp_path / "original")
    nonempty = tmp_path / "nonempty"
    nonempty.mkdir()
    (nonempty / "keep.txt").write_text("keep")
    for target in (str(nonempty), str(store.root / "nested"), "relative", str(tmp_path / "config"), str(Path.home())):
        with pytest.raises(ValueError):
            store.relocate(target)
    assert (nonempty / "keep.txt").read_text() == "keep"


def test_locator_failure_keeps_original_writable_and_complete_copy(tmp_path, monkeypatch):
    store = Store(tmp_path / "original")
    page = saved_page(store)
    def fail(_folder):
        raise OSError("Cannot save library selection")
    monkeypatch.setattr("visual_learning.storage.remember_data_dir", fail)
    target = tmp_path / "selected"
    with pytest.raises(OSError):
        store.relocate(str(target))
    assert store.get_generation(page["id"])
    assert Store(target).get_generation(page["id"])
    assert store.create_job({"kind": "import"})


def test_api_folder_switch_keeps_reader_available_and_new_jobs_in_selected_folder(tmp_path):
    app = create_app(tmp_path / "original")
    page = saved_page(app.state.store)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        client.headers["x-visual-learning"] = app.state.csrf_token
        result = client.put("/api/library/location", json={"path": str(tmp_path / "selected")})
        assert result.status_code == 200, result.text
        assert client.get("/api/settings").json()["storage"]["path"] == str(tmp_path / "selected")
        assert client.get(f"/api/generations/{page['id']}/page").status_code == 200
        assert client.get("/api/library").json()["generations"][0]["id"] == page["id"]
        response = client.post("/api/jobs", json={"url": "https://www.youtube.com/watch?v=L_Guz73e6fw", "regenerate": True})
        assert response.status_code == 201
        assert app.state.store.get_job(response.json()["job"]["id"])


def test_old_worker_connection_cannot_claim_after_move(tmp_path):
    store = Store(tmp_path / "original")
    worker = Worker(store)
    target = store.relocate(str(tmp_path / "selected"))
    target.create_job({"kind": "import"})
    with pytest.raises(LibraryRelocated):
        worker.run_once()
    assert target.claim_job("new-worker")
