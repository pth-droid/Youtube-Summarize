"""Real web/worker integration with authored semantic output, never cloud AI."""
from contextlib import asynccontextmanager
from pathlib import Path
import shutil
import os
import tempfile
import threading

import uvicorn

from tests_app.test_core import saved_page
from tests_app.test_learning import SemanticFixtureProvider
from distill.app import create_app
from distill.config import DEFAULT_SETTINGS
from distill.ingest import CaptionError
from distill.storage import Store
from distill.worker import Worker
import distill.ingest as ingest
import distill.providers as providers


def no_captions(*_a, **_k):
    raise CaptionError("no_captions", "Authored browser fixture: no captions. No network request was made.")


def main():
    with tempfile.TemporaryDirectory(prefix="distill-browser-") as workspace:
        data_dir = str(Path(workspace) / "library")
        os.environ["DISTILL_CONFIG_DIR"] = str(Path(workspace) / "config")
        store = Store(data_dir)
        # Browser checks never write test keys to the operator's credential store.
        import keyring
        test_keys = {}
        keyring.get_password = lambda service, name: test_keys.get((service, name))
        keyring.set_password = lambda service, name, value: test_keys.__setitem__((service, name), value)
        keyring.delete_password = lambda service, name: test_keys.pop((service, name), None)
        saved_page(store)
        # Include the genuine subscription-generated artifact when available.
        real = Path(".feasibility/pipeline-short/page.html")
        if real.is_file():
            job = store.create_job({"kind": "import", "preferences": DEFAULT_SETTINGS})
            target = store.artifact_dir(job["id"]) / "page.html"
            shutil.copyfile(real, target)
            store.publish_generation(job["id"], {"page_path": target, "source_id": "real-short", "title": "Real Codex source sample", "summary": "Source-grounded Vietnamese output generated with the subscription connector."})
        providers.make_provider = lambda *_a, **_k: SemanticFixtureProvider()
        ingest.fetch_youtube = no_captions
        worker = Worker(store)
        @asynccontextmanager
        async def lifespan(_app):
            thread = threading.Thread(target=worker.run_forever, daemon=True)
            thread.start()
            yield
            worker.stop()
            thread.join(timeout=5)
        app = create_app(data_dir)
        app.router.lifespan_context = lifespan
        uvicorn.run(app, host="127.0.0.1", port=8766, access_log=False, loop="distill.__main__:event_loop")


if __name__ == "__main__":
    main()
