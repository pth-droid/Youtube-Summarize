"""The loopback-only web service. Long processing belongs to the worker."""

from __future__ import annotations

import json
import asyncio
import hashlib
from contextlib import asynccontextmanager
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import os
import threading
from urllib.parse import urlparse
from typing import Annotated, Literal
import uuid

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .config import DEFAULT_SETTINGS, MAX_AUDIO_BYTES, MAX_IMPORT_BYTES, default_data_dir
from .storage import ACTIVE_STATES, Store

WEB = Path(__file__).with_name("web")
ProviderName = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")]
KeyProvider = ProviderName


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class APIConnection(StrictModel):
    name: str = Field("", max_length=120)
    endpoint: str = Field("", max_length=2000)
    model: str = Field("", max_length=100)
    protocol: Literal["openai", "anthropic"] = "openai"
    json_mode: bool = True
    token_parameter: Literal["max_tokens", "max_completion_tokens"] = "max_tokens"
    requires_key: bool = True

    @field_validator("endpoint")
    @classmethod
    def check_endpoint(cls, value):
        from .provider_config import validate_endpoint
        return validate_endpoint(value)


class ConnectionWrite(APIConnection):
    name: str = Field(min_length=1, max_length=120)
    endpoint: str = Field(min_length=1, max_length=2000)
    model: str = Field(min_length=1, max_length=100)
    api_key: str = Field("", max_length=4096, repr=False)

    @field_validator("name", "model", "endpoint")
    @classmethod
    def required_text(cls, value):
        if not value.strip():
            raise ValueError("Enter a name, endpoint, and model.")
        return value.strip()


class Preferences(StrictModel):
    provider: ProviderName | None = None
    language: Literal["vi", "en"] | None = None
    output_language: Literal["vi", "en"] | None = None
    source_language: str | None = Field(None, max_length=40)
    knowledge_level: Literal["beginner", "balanced", "advanced"] | None = None
    learning_goal: str | None = Field(None, max_length=2000)
    codex_model: str | None = Field(None, max_length=100)
    claude_code_model: str | None = Field(None, max_length=100)
    deepseek_model: str | None = Field(None, max_length=100)
    api_connections: dict[ProviderName, APIConnection] | None = None
    output_format: Literal["page", "lecture"] | None = None
    slide_theme: Literal["forest", "maroon"] | None = None
    transcription_providers: dict[Literal["video", "meeting", "lecture"], Literal["soniox", "groq"]] | None = None
    soniox_model: str | None = Field(None, pattern=r"^stt-async-[a-z0-9.-]{1,40}$")
    groq_model: Literal["whisper-large-v3", "whisper-large-v3-turbo"] | None = None
    groq_free_only: bool | None = None
    allow_paid_llm: bool | None = None
    retain_audio: bool | None = None

    @field_validator("api_connections")
    @classmethod
    def connection_ids(cls, value):
        if value and {"codex", "claude_code", "deepseek", "groq", "soniox"}.intersection(value):
            raise ValueError("This connection ID is reserved.")
        return value


class NewJob(StrictModel):
    url: str = Field(min_length=1, max_length=2000)
    preferences: Preferences = Field(default_factory=Preferences)
    paid_usage_approved: bool = False
    regenerate: bool = False


class RetryJob(StrictModel):
    provider: ProviderName | None = None
    paid_usage_approved: bool = False
    source_language: str | None = Field(None, max_length=40)


class AudioConsent(StrictModel):
    approved: Literal[True]
    free_account_confirmed: bool = False
    paid_usage_approved: bool = False


class Credential(StrictModel):
    key: str = Field(min_length=1, max_length=4096)


class LibraryLocation(StrictModel):
    path: str = Field(min_length=1, max_length=4096)


def public_job(job: dict) -> dict:
    return {key: value for key, value in job.items() if key not in {"lease_owner", "lease_until", "heartbeat"}}


def made_as(values: dict) -> tuple:
    """What a generation is, or a request asks for: a page, or slides in one look (decks before looks are forest)."""
    if values.get("output_format", "page") != "lecture":
        return ("page",)
    return ("lecture", values.get("slide_theme") or "forest")


def create_app(data_dir: Path | str | None = None, *, auto_worker: bool = False) -> FastAPI:
    store = Store(data_dir or default_data_dir())
    token = secrets.token_urlsafe(32)
    folder_picker_lock = threading.Lock()
    @asynccontextmanager
    async def lifespan(application):
        if auto_worker:
            command = [sys.executable, "-m", "distill.worker", "--data-dir", str(store.root)]
            application.state.worker_process = subprocess.Popen(command, cwd=Path(__file__).parent.parent, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        try:
            yield
        finally:
            process = application.state.worker_process
            if process and process.poll() is None:
                from .providers import stop_process
                stop_process(process)
    app = FastAPI(title="Distill", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.store = store
    app.state.csrf_token = token
    app.state.worker_process = None
    library_gate = asyncio.Lock()

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        hostname = request.url.hostname
        if hostname not in {"127.0.0.1", "localhost", "::1"}:
            return JSONResponse({"detail": "This app accepts local requests only."}, status_code=403)
        origin = request.headers.get("origin")
        expected = f"{request.url.scheme}://{request.url.netloc}"
        if origin and origin != expected:
            return JSONResponse({"detail": "This request came from a different site."}, status_code=403)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if not secrets.compare_digest(request.headers.get("x-distill", ""), token):
                return JSONResponse({"detail": "Refresh the app and try again."}, status_code=403)
        content_length = request.headers.get("content-length")
        limit = MAX_AUDIO_BYTES + MAX_IMPORT_BYTES if request.url.path.startswith("/api/audio-import") else MAX_IMPORT_BYTES + 1024 * 1024
        if content_length:
            try:
                if int(content_length) < 0 or int(content_length) > limit:
                    return JSONResponse({"detail": "This file is too large."}, status_code=413)
            except ValueError:
                return JSONResponse({"detail": "Invalid request length."}, status_code=400)
        # Library moves and other API operations cannot overlap inside this service.
        if request.url.path.startswith("/api/"):
            async with library_gate:
                response = await call_next(request)
        else:
            response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        if not request.url.path.endswith("/page"):
            response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        return response

    @app.exception_handler(RequestValidationError)
    async def safe_validation(_request, error):
        # FastAPI's default response repeats submitted values, including API keys.
        return JSONResponse({"detail": "Check the form values and try again.", "fields": [".".join(str(part) for part in item["loc"]) for item in error.errors()]}, status_code=422)

    def job_or_404(job_id):
        job = store.get_job(job_id)
        if not job:
            raise HTTPException(404, "This job was not found.")
        return job

    def generation_or_404(generation_id):
        result = store.get_generation(generation_id)
        if not result:
            raise HTTPException(404, "This saved page was not found.")
        return result

    def preferences(values: Preferences | dict, *, paid_usage_approved=False):
        values = values.model_dump(exclude_none=True) if isinstance(values, Preferences) else values
        defaults = store.settings()
        merged = defaults | values
        if "output_language" in values and "language" not in values:
            merged["language"] = values["output_language"]
        merged["output_language"] = merged["language"]
        check_provider(merged["provider"], merged)
        from .provider_config import SUBSCRIPTION_PROVIDERS, selected_model
        merged["model"] = selected_model(merged, merged["provider"])
        if merged["provider"] not in SUBSCRIPTION_PROVIDERS and not (paid_usage_approved or defaults.get("allow_paid_llm")):
            raise HTTPException(409, "Approve API use for this page before continuing. Hosted providers may charge.")
        merged["paid_usage_approved"] = bool(paid_usage_approved or defaults.get("allow_paid_llm"))
        return merged

    def safe_provider_error(error):
        return HTTPException(400, str(error)[:400])

    def check_provider(provider, settings):
        from .provider_config import BUILT_IN_PROVIDERS
        if provider not in BUILT_IN_PROVIDERS and provider not in settings.get("api_connections", {}):
            raise HTTPException(409, "This connection is unavailable. Add it in Provider access or select another connection.")

    @app.get("/", response_class=HTMLResponse)
    def home():
        content = (WEB / "index.html").read_text(encoding="utf-8")
        return HTMLResponse(content.replace("__CSRF_TOKEN__", token))

    ytdlp_updating = threading.Lock()

    @app.get("/api/health")
    def health():
        process = app.state.worker_process
        return {"status": "ok", "worker": "running" if process and process.poll() is None else "stopped" if auto_worker else "external", "storage": str(store.root)}

    @app.get("/api/settings")
    def read_settings():
        from .providers import SecretStore
        settings = store.settings()
        secrets_store = SecretStore()
        credentials = secrets_store.status()
        credentials.update({name: secrets_store.status(name) for name in settings.get("api_connections", {})})
        from .downloader import installed_version
        tools = {name: bool(shutil.which(name)) for name in ("codex", "claude", "ffmpeg", "deno")}
        tools["yt-dlp"] = installed_version() is not None  # the app runs yt-dlp from its own environment, not PATH
        return {"preferences": settings, "credentials": credentials, "tools": tools, "storage": store.storage_info()}

    @app.get("/api/tools/yt-dlp")
    def ytdlp_status(check: bool = False):
        from .downloader import status
        return status(check_latest=check)

    @app.post("/api/tools/yt-dlp/update")
    def ytdlp_update():
        from .downloader import DownloadError, status, update
        # A running download reads the files an update replaces.
        if any(job["state"] in {"retrieving", "transcribing"} for job in store.list_jobs()):
            raise HTTPException(409, "Wait for the current caption or audio download to finish, then update yt-dlp.")
        if not ytdlp_updating.acquire(blocking=False):
            raise HTTPException(409, "An update of yt-dlp is already running.")
        try:
            result = update()
        except DownloadError as error:
            lines = error.diagnostics.get("error_lines", [])
            raise HTTPException(502, error.message + (" " + lines[-1] if lines else ""))
        finally:
            ytdlp_updating.release()
        return status() | result

    @app.put("/api/settings")
    def update_settings(value: Preferences):
        values = value.model_dump(exclude_none=True)
        check_provider(values.get("provider", store.settings()["provider"]), store.settings() | values)
        if "language" in values:
            values["output_language"] = values["language"]
        elif "output_language" in values:
            values["language"] = values["output_language"]
        return {"preferences": store.save_settings(values)}

    def save_connection(connection_id, value):
        from .providers import ProviderError, SecretStore
        connection = value.model_dump(exclude={"api_key"})
        if value.api_key:
            try:
                SecretStore().set(connection_id, value.api_key)
            except ProviderError as error:
                raise safe_provider_error(error)
        connections = store.settings().get("api_connections", {}) | {connection_id: connection}
        store.save_settings({"api_connections": connections})
        return {"id": connection_id, "connection": connection}

    def check_connection_idle(connection_id):
        if any(job["state"] not in {"complete", "failed", "cancelled"} and job["input"].get("preferences", {}).get("provider") == connection_id for job in store.list_jobs()):
            raise HTTPException(409, "Finish or cancel jobs using this connection before changing or removing it.")

    @app.post("/api/connections", status_code=201)
    def add_connection(value: ConnectionWrite):
        return save_connection("api_" + uuid.uuid4().hex, value)

    @app.put("/api/connections/{connection_id}")
    def edit_connection(connection_id: ProviderName, value: ConnectionWrite):
        if connection_id not in store.settings().get("api_connections", {}):
            raise HTTPException(404, "This connection was not found.")
        check_connection_idle(connection_id)
        return save_connection(connection_id, value)

    @app.delete("/api/connections/{connection_id}")
    def delete_connection(connection_id: ProviderName):
        settings = store.settings()
        connections = settings.get("api_connections", {}).copy()
        if connection_id not in connections:
            raise HTTPException(404, "This connection was not found.")
        check_connection_idle(connection_id)
        from .providers import ProviderError, SecretStore
        try:
            secret_store = SecretStore()
            if secret_store.get(connection_id):
                secret_store.delete(connection_id)
        except ProviderError as error:
            raise safe_provider_error(error)
        del connections[connection_id]
        values = {"api_connections": connections}
        if settings["provider"] == connection_id:
            values["provider"] = "codex"
        store.save_settings(values)
        return {"deleted": True, "default_provider": values.get("provider", settings["provider"])}

    def check_key_provider(provider):
        from .providers import SecretStore
        if provider not in SecretStore.env_names and provider not in store.settings().get("api_connections", {}):
            raise HTTPException(404, "This connection was not found.")

    @app.put("/api/credentials/{provider}")
    def save_credential(provider: KeyProvider, value: Credential):
        check_key_provider(provider)
        from .providers import ProviderError, SecretStore
        secret_store = SecretStore()
        try:
            secret_store.set(provider, value.key)
        except ProviderError as error:
            raise safe_provider_error(error)
        return secret_store.status(provider)

    @app.delete("/api/credentials/{provider}")
    def remove_credential(provider: KeyProvider):
        check_key_provider(provider)
        from .providers import ProviderError, SecretStore
        secret_store = SecretStore()
        try:
            secret_store.delete(provider)
        except ProviderError as error:
            raise safe_provider_error(error)
        return secret_store.status(provider)

    @app.get("/api/library")
    def library(q: str = "", language: str = ""):
        return {"generations": store.library(q[:2000], language)}

    @app.post("/api/library/browse")
    def browse_library_folder():
        if os.name != "nt":
            raise HTTPException(409, "Folder browsing is available in the Windows local app. Enter a path here.")
        if not folder_picker_lock.acquire(blocking=False):
            raise HTTPException(409, "A folder picker is already open.")
        try:
            result = subprocess.run([sys.executable, "-m", "distill.folder_picker"], input=json.dumps({"initialdir": str(store.root)}), capture_output=True, text=True, timeout=180, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode:
                raise HTTPException(409, "The folder picker could not open. Enter the folder path instead.")
            return json.loads(result.stdout)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            raise HTTPException(409, "Folder browsing did not finish. Enter the folder path instead.") from None
        finally:
            folder_picker_lock.release()

    @app.put("/api/library/location")
    def change_library_location(value: LibraryLocation):
        nonlocal store
        old_path = str(store.root)
        try:
            store = store.relocate(value.path)
        except (ValueError, OSError) as error:
            raise HTTPException(409, str(error)[:500])
        app.state.store = store
        return {"storage": store.storage_info(), "previous_path": old_path, "message": "Library folder saved. The original folder is kept as a backup. New pages use the selected folder."}

    @app.get("/api/jobs")
    def jobs():
        return {"jobs": [public_job(job) for job in store.list_jobs()]}

    @app.post("/api/jobs", status_code=201)
    def new_job(value: NewJob):
        from .ingest import CaptionError, parse_youtube_id
        try:
            video_id = parse_youtube_id(value.url)
        except (CaptionError, ValueError) as error:
            raise HTTPException(422, str(error))
        existing = store.find_existing(video_id)
        if existing and not value.regenerate:
            return {"existing": existing, "job": None}
        selected = preferences(value.preferences, paid_usage_approved=value.paid_usage_approved)
        job = store.create_job({"kind": "youtube", "video_id": video_id, "url": "https://www.youtube.com/watch?v=" + video_id, "preferences": selected}, state="awaiting_approval")
        # Reuse a validated source across language/model/goal changes. The first page, the first slides
        # or the first slides in another look keep a compatible analysis; a new version gets a fresh one.
        if existing:
            source = store.load_checkpoint(existing[0]["job_id"], "source")
            if source and (not selected.get("source_language") or source.get("language", "").lower() == selected["source_language"].lower()):
                store.checkpoint(job["id"], "source", source)
                store.write_json(job["id"], "source.json", source)
                if all(made_as(g["metadata"]) != made_as(selected) for g in existing):
                    # Slides in the same format bring their lecture plan too, so a new look only renders again.
                    donor = next((g for g in existing if g["metadata"].get("output_format", "page") == selected["output_format"]), existing[0])
                    store.copy_checkpoints(donor["job_id"], job["id"])
        job = store.update_job(job["id"], state="queued")
        return {"job": public_job(job), "existing": []}

    @app.get("/api/jobs/{job_id}")
    def read_job(job_id: str):
        return public_job(job_or_404(job_id))

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str):
        job_or_404(job_id)
        try:
            return public_job(store.cancel(job_id))
        except ValueError as error:
            raise HTTPException(409, str(error))

    @app.post("/api/jobs/{job_id}/retry")
    def retry_job(job_id: str, value: RetryJob):
        job = job_or_404(job_id)
        if job["state"] in ACTIVE_STATES | {"queued", "complete"}:
            raise HTTPException(409, "This job is already running or complete.")
        job_input = job["input"]
        selected = job_input["preferences"].copy()
        changed = value.provider and value.provider != selected["provider"]
        if changed:
            selected["provider"] = value.provider
            from .provider_config import selected_model
            selected["api_connections"] = store.settings().get("api_connections", {})
            selected["model"] = selected_model(store.settings(), value.provider)
        from .provider_config import is_api_provider, selected_model
        check_provider(selected["provider"], store.settings())
        if is_api_provider(selected, selected["provider"]):
            current_connections = store.settings().get("api_connections", {})
            provider_name = selected["provider"]
            changed = changed or selected.get("api_connections", {}).get(provider_name) != current_connections.get(provider_name)
            selected["api_connections"] = current_connections
            selected["model"] = selected_model(store.settings(), provider_name)
        language_changed = value.source_language is not None and value.source_language != selected.get("source_language")
        if language_changed:
            if job_input["kind"] != "youtube":
                raise HTTPException(409, "Import a new source to change its transcription language. Saved imported text stays attached to its original source.")
            selected["source_language"] = value.source_language
            if job_input["kind"] == "youtube":
                job["approval"] = None
        from .provider_config import SUBSCRIPTION_PROVIDERS
        if selected["provider"] not in SUBSCRIPTION_PROVIDERS and not (value.paid_usage_approved or (not changed and selected.get("paid_usage_approved")) or store.settings()["allow_paid_llm"]):
            raise HTTPException(409, "Approve API use before retrying with this provider.")
        selected["paid_usage_approved"] = bool(value.paid_usage_approved or (not changed and selected.get("paid_usage_approved")) or store.settings()["allow_paid_llm"])
        if language_changed:
            store.clear_checkpoints(job_id, ())
        elif changed:
            store.clear_checkpoints(job_id, ("source",))
        job_input["preferences"] = selected
        return public_job(store.update_job(job_id, input=job_input, state="queued", approval=job.get("approval"), cancel_requested=False, error=None, lease_owner=None, lease_until=None, next_run_at=0, progress={"stage": "queued", "message": "Queued. Completed work will be reused where compatible."}))

    @app.post("/api/jobs/{job_id}/approve")
    def approve_audio(job_id: str, value: AudioConsent):
        job = job_or_404(job_id)
        if job["state"] != "awaiting_approval" or not job.get("approval"):
            raise HTTPException(409, "This job is not waiting for audio approval.")
        approval = job["approval"]
        if approval.get("free_only", True) and not value.free_account_confirmed:
            raise HTTPException(409, "Confirm that this Groq account has no paid billing before using the free-only route.")
        if not approval.get("free_only", True) and not value.paid_usage_approved:
            raise HTTPException(409, "Approve paid transcription before continuing.")
        approval.update({"approved": True, "free_account_confirmed": value.free_account_confirmed, "paid_usage_approved": value.paid_usage_approved})
        return public_job(store.update_job(job_id, approval=approval, state="queued", error=None, next_run_at=0, progress={"stage": "queued", "message": "Audio approved. Waiting for the worker."}))

    async def read_import(file: UploadFile, limit=MAX_IMPORT_BYTES) -> bytes:
        data = await file.read(limit + 1)
        await file.close()
        if len(data) > limit:
            raise HTTPException(413, "This transcript is too large. The limit is 20 MB.")
        if not data:
            raise HTTPException(422, "This file is empty.")
        return data

    def parsed_import(data, filename, title, url, language):
        from .ingest import CaptionError, parse_import, parse_youtube_id
        metadata = {"title": title.strip()[:500] or Path(filename).stem, "language": language}
        if url and url.strip():
            try:
                video_id = parse_youtube_id(url)
            except (CaptionError, ValueError) as error:
                raise HTTPException(422, str(error))
            metadata.update({"video_id": video_id, "url": "https://www.youtube.com/watch?v=" + video_id})
        try:
            result = parse_import(data, filename, metadata)
            return result.model_dump(mode="json") if hasattr(result, "model_dump") else result
        except ValueError as error:
            raise HTTPException(422, str(error)[:400])

    @app.post("/api/import", status_code=201)
    async def import_transcript(file: UploadFile = File(...), title: str = Form(""), url: str = Form(""), language: str = Form("unknown"), preference_json: str = Form("{}"), paid_usage_approved: bool = Form(False)):
        data = await read_import(file)
        source = parsed_import(data, file.filename or "transcript.txt", title, url, language)
        try:
            value = Preferences.model_validate_json(preference_json)
        except ValueError:
            raise HTTPException(422, "Check the import preferences.")
        selected = preferences(value, paid_usage_approved=paid_usage_approved)
        # Publish to the worker queue only after the durable source is ready.
        job = store.create_job({"kind": "import", "video_id": source.get("video_id"), "url": source.get("url"), "preferences": selected, "title": source["title"]}, state="awaiting_approval")
        store.checkpoint(job["id"], "source", source)
        store.write_json(job["id"], "source.json", source)
        job = store.update_job(job["id"], state="queued")
        return {"job": public_job(job)}

    @app.post("/api/jobs/{job_id}/import")
    async def recover_import(job_id: str, file: UploadFile = File(...)):
        job = job_or_404(job_id)
        if job["state"] in ACTIVE_STATES | {"queued", "complete"}:
            raise HTTPException(409, "Wait for processing to stop before importing a replacement transcript.")
        source = parsed_import(await read_import(file), file.filename or "transcript.txt", job["input"].get("title", "Imported transcript"), job["input"].get("url", ""), job["input"]["preferences"].get("source_language") or "unknown")
        store.clear_checkpoints(job_id, ())
        store.checkpoint(job_id, "source", source)
        store.write_json(job_id, "source.json", source)
        return public_job(store.update_job(job_id, state="queued", error=None, cancel_requested=False, next_run_at=0, approval=None, progress={"stage": "queued", "message": "Transcript imported. Waiting for analysis."}))

    @app.post("/api/audio-import", status_code=201)
    async def import_audio(file: UploadFile = File(...), title: str = Form(""), preference_json: str = Form("{}"), paid_usage_approved: bool = Form(False), recording_type: str = Form("meeting")):
        allowed = {".wav", ".mp3", ".m4a", ".webm", ".ogg", ".opus", ".flac", ".mp4"}
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in allowed:
            await file.close()
            raise HTTPException(422, "Choose a WAV, MP3, M4A, WebM, OGG, Opus, FLAC, or MP4 audio file.")
        if recording_type not in ("meeting", "lecture"):
            await file.close()
            raise HTTPException(422, "Choose whether this recording is a meeting or a lecture.")
        try:
            value = Preferences.model_validate_json(preference_json)
        except ValueError:
            await file.close()
            raise HTTPException(422, "Check the import preferences.")
        selected = preferences(value, paid_usage_approved=paid_usage_approved)
        job = store.create_job({"kind": "audio_import", "title": title.strip()[:500] or Path(file.filename).stem, "recording_type": recording_type, "preferences": selected}, state="awaiting_approval")
        audio_path = store.artifact_dir(job["id"]) / ("imported-audio" + suffix)
        total, digest = 0, hashlib.sha256()
        try:
            with audio_path.open("wb") as destination:
                while chunk := await file.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_AUDIO_BYTES:
                        raise HTTPException(413, "This audio file is too large. The limit is 1 GB.")
                    digest.update(chunk)
                    destination.write(chunk)
            if not total:
                raise HTTPException(422, "This audio file is empty.")
        except Exception:
            audio_path.unlink(missing_ok=True)
            store.update_job(job["id"], state="cancelled", cancel_requested=True)
            raise
        finally:
            await file.close()
        source_id = "import:" + digest.hexdigest()
        input_data = job["input"] | {"audio_source": source_id, "audio_path": str(audio_path.relative_to(store.root))}
        from .audio import PROVIDER_LABELS, approval_request
        approval = approval_request(selected, job["id"], source_id, "Audio import needs cloud speech transcription.", workflow=recording_type)
        job = store.update_job(job["id"], input=input_data, approval=approval, state="awaiting_approval", progress={"stage": "awaiting_approval", "message": f"Audio is saved locally. Approve sending it to {PROVIDER_LABELS[approval['provider']]} before processing."})
        return {"job": public_job(job)}

    @app.delete("/api/jobs/{job_id}/audio")
    def delete_audio(job_id: str):
        job = job_or_404(job_id)
        if job["state"] in ACTIVE_STATES | {"queued"}:
            raise HTTPException(409, "Cancel processing and wait for it to stop before deleting temporary audio.")
        folder = store.artifact_dir(job_id)
        for pattern in ("imported-audio.*", "source-audio.*", "chunks/*.wav", "chunks/*.flac"):
            for path in folder.glob(pattern):
                store.managed_path(path).unlink(missing_ok=True)
        return {"deleted": True}

    @app.get("/api/generations/{generation_id}/page")
    def learning_page(generation_id: str):
        result = generation_or_404(generation_id)
        path = store.managed_path(result["page_path"])
        if not path.is_file():
            raise HTTPException(410, "The saved page file is missing. Restore a backup or generate a new page.")
        return FileResponse(path, media_type="text/html; charset=utf-8", headers={"Content-Security-Policy": "sandbox allow-scripts allow-popups allow-popups-to-escape-sandbox; default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; font-src data:; object-src 'none'; base-uri 'none'"})

    @app.get("/api/generations/{generation_id}/details")
    def generation_details(generation_id: str):
        result = generation_or_404(generation_id)
        record = {}
        path = result.get("metadata", {}).get("generation_path")
        if path:
            try:
                record = json.loads(store.managed_path(path).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass
        entries = [value for value in record.get("usage", []) if isinstance(value, dict)]
        def sum_tokens(primary, fallback):
            values = [entry.get(primary, entry.get(fallback)) for entry in entries]
            values = [value for value in values if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0]
            return sum(values) if values else None
        return {"provider": result["provider"], "provider_name": result.get("metadata", {}).get("provider_name"), "model": record.get("model") or result["model"] or "Provider default", "duration_seconds": record.get("duration_seconds"), "usage_records": len(entries), "input_tokens": sum_tokens("input_tokens", "prompt_tokens"), "output_tokens": sum_tokens("output_tokens", "completion_tokens"), "usage_scope": "Available usage records from the latest processing run. Earlier checkpoint work may not be included.", "subscription_allowance": "Unknown", "billed_cost": "Unavailable"}

    @app.get("/api/generations/{generation_id}/export")
    def export_page(generation_id: str):
        result = generation_or_404(generation_id)
        path = store.managed_path(result["page_path"])
        if not path.is_file():
            raise HTTPException(410, "The saved page file is missing.")
        name = "lecture-slides-" if result.get("metadata", {}).get("output_format") == "lecture" else "learning-page-"
        return FileResponse(path, media_type="text/html", filename=name + generation_id[:8] + ".html")

    @app.delete("/api/generations/{generation_id}")
    def delete_page(generation_id: str):
        generation_or_404(generation_id)
        store.delete_generation(generation_id)
        return {"deleted": True}

    @app.post("/api/backup")
    def backup():
        try:
            path = store.backup()
        except ValueError as error:
            raise HTTPException(409, str(error))
        return FileResponse(path, media_type="application/zip", filename=path.name)

    app.mount("/static", StaticFiles(directory=WEB), name="static")
    return app
