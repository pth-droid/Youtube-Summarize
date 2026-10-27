"""A single durable worker. It runs independently of the browser and web service."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
import signal
import sqlite3
import threading
import time
import traceback
import uuid

from .config import default_data_dir
from .storage import ACTIVE_STATES, LibraryRelocated, Store

LOGGER = logging.getLogger(__name__)


def normalized(value):
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else value


class Worker:
    def __init__(self, store: Store, *, lease_seconds: int = 90):
        self.store = store
        self.owner = f"{os.getpid()}-{uuid.uuid4().hex[:10]}"
        self.lease_seconds = lease_seconds
        self.stop_event = threading.Event()
        self.next_cleanup = 0

    def stop(self, *_):
        self.stop_event.set()

    def update_job(self, job_id: str, **fields):
        return self.store.update_job(job_id, expected_owner=self.owner, **fields)

    def run_forever(self):
        while not self.stop_event.is_set():
            try:
                if time.time() >= self.next_cleanup:
                    self.store.cleanup_audio()
                    self.next_cleanup = time.time() + 300
                processed = self.run_once()
            except sqlite3.OperationalError:
                # A large owner-requested backup can hold the writer gate longer
                # than one SQLite wait. Remain available instead of exiting.
                LOGGER.info("Library busy. Waiting before checking saved jobs.")
                self.stop_event.wait(5)
                continue
            except LibraryRelocated as moved:
                self.store = Store(moved.destination)
                self.next_cleanup = 0
                LOGGER.info("Library folder changed. Processing will use the selected folder.")
                continue
            if not processed:
                self.stop_event.wait(1)

    def run_once(self) -> bool:
        job = self.store.claim_job(self.owner, self.lease_seconds)
        if not job:
            return False
        job_id = job["id"]
        heartbeat_stop = threading.Event()

        def heartbeat():
            while not heartbeat_stop.wait(max(1, self.lease_seconds / 3)):
                self.store.heartbeat(job_id, self.owner, self.lease_seconds)

        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()
        try:
            self.process(job)
        except (InterruptedError, KeyboardInterrupt):
            current = self.store.get_job(job_id)
            if current and current["lease_owner"] == self.owner:
                state = "cancelled" if current["cancel_requested"] else "queued"
                self.update_job(job_id, state=state, progress={"stage": state, "message": "Processing cancelled." if state == "cancelled" else "Paused. The next worker launch will resume from saved work."})
        except Exception as exc:
            self._handle_error(job_id, exc)
        finally:
            heartbeat_stop.set()
            thread.join(timeout=2)
            self.store.release(job_id, self.owner)
        return True

    def _handle_error(self, job_id: str, error: Exception):
        # Connector messages are safe, public messages. Unexpected exceptions stay generic.
        code = getattr(error, "code", None)
        message = getattr(error, "message", None) or (str(error) if code else None)
        retry_after = getattr(error, "retry_after", None)
        diagnostics = getattr(error, "diagnostics", None)
        if not code:
            frames = traceback.extract_tb(error.__traceback__)[-5:] if error.__traceback__ else []
            diagnostics = dict(diagnostics or {}) | {"exception_type": type(error).__name__, "stack": [
                {"file": Path(frame.filename).name, "function": frame.name, "line": frame.lineno}
                for frame in frames]}
        current = self.store.get_job(job_id)
        if not current or current["lease_owner"] != self.owner:
            return
        if self.stop_event.is_set() or current["cancel_requested"] or code == "cancelled" or type(error).__name__ == "PipelineCancelled":
            state = "cancelled" if current["cancel_requested"] else "queued"
            self.update_job(job_id, state=state, error=None, next_run_at=0, progress={"stage": state, "message": "Processing cancelled." if state == "cancelled" else "Paused. Saved work will resume at the next launch."})
            return
        quota = code in {"quota", "rate_limit", "quota_exhausted", "rate_limited"}
        temporary = code in {"temporary", "timeout"}
        failures = (current.get("error") or {}).get("temporary_failures", 0) + 1 if temporary else 0
        if quota or (temporary and failures < 3):
            seconds = max(5, min(float(retry_after or 60), 86400))
            if temporary:
                seconds = min(300, seconds * (2 ** (failures - 1)))
            self.update_job(job_id, state="waiting_for_quota", next_run_at=time.time() + seconds, error={"code": code, "message": message or "The provider asked us to wait. Saved work will resume after the wait.", "retry_after": seconds, "temporary_failures": failures}, progress={"stage": "waiting_for_quota", "message": "Waiting for provider quota. Your completed work is saved." if quota else f"Connection interrupted. Automatic retry {failures} of 2 is scheduled."})
            return
        if code in {"approval_required", "audio_approval_required", "audio_approval"}:
            self.update_job(job_id, state="awaiting_approval", error={"code": code, "message": message or str(error)})
            return
        safe_pipeline_error = type(error).__module__ == "distill.pipeline" and type(error).__name__ == "PipelineError"
        safe_message = message or (str(error) if isinstance(error, (ValueError, FileNotFoundError)) or safe_pipeline_error else "Processing could not finish. Your transcript and completed sections are saved. Retry, switch provider, or import a transcript.")
        error_record = {"code": code or "processing_failed", "message": safe_message[:1000]}
        if isinstance(diagnostics, dict) and diagnostics:
            error_record["diagnostics"] = diagnostics
        self.update_job(job_id, state="failed", error=error_record, progress={"stage": "failed", "message": "Processing stopped. Saved work is ready for retry."})
        LOGGER.warning("Job %s failed (%s)", job_id, type(error).__name__)

    def process(self, job: dict):
        from .ingest import CaptionError, fetch_youtube
        from .models import Transcript
        from .pipeline import Pipeline
        from .providers import make_provider

        job_id = job["id"]
        work_dir = self.store.artifact_dir(job_id)
        preferences = job["input"]["preferences"]
        source = self.store.load_checkpoint(job_id, "source")

        def cancelled():
            current = self.store.get_job(job_id)
            return self.stop_event.is_set() or not current or current["cancel_requested"] or current["lease_owner"] != self.owner

        def progress(stage, detail=None, **extra):
            if cancelled():
                raise InterruptedError("Processing cancelled or paused")
            if isinstance(stage, dict):
                event = stage | extra
                stage = event.get("stage", "analyzing")
            else:
                event = ({"message": detail} if isinstance(detail, str) else detail or {}) | extra
            aliases = {"selecting visuals": "selecting_visuals", "visuals": "selecting_visuals", "segmentation": "analyzing", "extracting": "analyzing", "synthesizing": "analyzing", "grounding": "validating"}
            stage = aliases.get(stage, stage)
            if stage not in ACTIVE_STATES:
                stage = "analyzing"
            self.update_job(job_id, state=stage, progress={"stage": stage} | event)

        def checkpoint(name, value):
            if cancelled():
                raise InterruptedError("Processing cancelled or paused")
            self.store.checkpoint(job_id, name, normalized(value), expected_owner=self.owner)

        def load_checkpoint(name):
            return self.store.load_checkpoint(job_id, name)

        if not source:
            progress("retrieving", {"message": "Retrieving captions with original timestamps."})
            approval = job.get("approval") or {}
            audio_source = job["input"].get("audio_source") or job["input"].get("video_id")
            approved_audio = approval.get("approved") and approval.get("source") == audio_source
            if approved_audio:
                from .audio import transcribe_file, transcribe_youtube
                progress("transcribing", {"message": "Transcribing approved audio. Original timing is preserved."})
                def audio_progress(message):
                    progress("transcribing", message)
                if job["input"]["kind"] == "audio_import":
                    source = normalized(transcribe_file(self.store.managed_path(job["input"]["audio_path"]), work_dir, approval, progress=audio_progress, cancelled=cancelled, checkpoint=checkpoint, load_checkpoint=load_checkpoint))
                    source["title"] = job["input"].get("title") or source["title"]
                else:
                    source = normalized(transcribe_youtube(job["input"]["video_id"], work_dir, approval, progress=audio_progress, cancelled=cancelled, checkpoint=checkpoint, load_checkpoint=load_checkpoint))
            elif job["input"]["kind"] == "audio_import":
                self.update_job(job_id, state="awaiting_approval", progress={"stage": "awaiting_approval", "message": "Approve sending this audio for transcription, or import a transcript."})
                return
            else:
                try:
                    source = normalized(fetch_youtube(job["input"]["video_id"], source_language=preferences.get("source_language") or None))
                except CaptionError as error:
                    if cancelled():
                        raise InterruptedError()
                    if getattr(error, "retry_after", None):
                        raise
                    from .audio import approval_request
                    request = approval_request(preferences, job_id, job["input"]["video_id"], getattr(error, "message", str(error)), languages=getattr(error, "languages", []), caption_error=getattr(error, "code", "unavailable"))
                    caption_error = {"code": request["caption_error"], "message": request["reason"]}
                    if getattr(error, "diagnostics", None):
                        caption_error["diagnostics"] = error.diagnostics  # why the free yt-dlp route failed too
                    self.update_job(job_id, state="awaiting_approval", approval=request, error=caption_error, progress={"stage": "awaiting_approval", "message": "Caption retrieval stopped. Choose audio transcription or import a transcript."})
                    return
            # Validate before saving the source checkpoint. Do not cache invalid ingestion.
            source = Transcript.model_validate(source).model_dump(mode="json")
            checkpoint("source", source)
            self.store.write_json(job_id, "source.json", source)
            if job["input"]["kind"] == "audio_import" and not preferences.get("retain_audio"):
                self.store.managed_path(job["input"]["audio_path"]).unlink(missing_ok=True)
        if cancelled():
            raise InterruptedError()
        provider = make_provider(preferences, cancelled=cancelled)
        from .model_profiles import resolve_profile
        try:
            provider.model_profile = resolve_profile(provider, self.store.root / "model-profiles.json")
        except (OSError, ValueError, TypeError) as error:
            from .providers import ProviderError
            raise ProviderError("configuration", "Check model-profiles.json in the library folder. Its model settings are invalid.") from error
        if hasattr(provider, "max_output_tokens"):
            provider.max_output_tokens = provider.model_profile.output_tokens
        result = Pipeline(provider).run(source, preferences, work_dir, progress=progress, cancelled=cancelled, checkpoint=checkpoint, load_checkpoint=load_checkpoint)
        if cancelled():
            raise InterruptedError()
        self.store.publish_generation(job_id, result, expected_owner=self.owner)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Process Distill jobs independently of the browser.")
    parser.add_argument("--data-dir", type=Path, default=default_data_dir())
    parser.add_argument("--once", action="store_true", help="Process at most one ready job.")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    worker = Worker(Store(args.data_dir))
    signal.signal(signal.SIGINT, worker.stop)
    signal.signal(signal.SIGTERM, worker.stop)
    if args.once:
        worker.run_once()
    else:
        worker.run_forever()


if __name__ == "__main__":
    main()
