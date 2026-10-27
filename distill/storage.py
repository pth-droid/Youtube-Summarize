"""Durable local jobs and artifacts with short, process-local SQLite transactions."""

from __future__ import annotations

from contextlib import closing, contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time
import uuid
import zipfile
import shutil

from .config import DEFAULT_SETTINGS, app_config_dir, remember_data_dir

TERMINAL_STATES = {"complete", "failed", "cancelled"}
BLOCKED_STATES = {"awaiting_approval", "waiting_for_quota"}
ACTIVE_STATES = {"retrieving", "transcribing", "analyzing", "selecting_visuals", "validating", "rendering"}
VALID_STATES = TERMINAL_STATES | BLOCKED_STATES | ACTIVE_STATES | {"queued"}
SAFE_NAME = re.compile(r"^[a-zA-Z0-9_.-]{1,180}$")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_text(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


class LibraryRelocated(RuntimeError):
    def __init__(self, destination):
        self.destination = destination
        super().__init__("The library has moved to " + destination)


class Store:
    def __init__(self, root: Path | str):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "library.sqlite3"
        # An old library remains a backup. Never resume writes to that backup.
        visited = set()
        while self.db_path.is_file():
            if self.root in visited:
                raise ValueError("The saved library location contains a loop.")
            visited.add(self.root)
            with closing(sqlite3.connect(self.db_path)) as con:
                exists = con.execute("SELECT 1 FROM sqlite_master WHERE name='library_location'").fetchone()
                moved = con.execute("SELECT destination FROM library_location LIMIT 1").fetchone() if exists else None
            if not moved:
                break
            self.root = Path(moved[0]).resolve()
            self.db_path = self.root / "library.sqlite3"
            if not self.db_path.is_file():
                raise ValueError("The selected library is unavailable. Restore its folder before starting.")
        (self.root / "jobs").mkdir(exist_ok=True)
        self._initialize()

    @contextmanager
    def connection(self):
        con = sqlite3.connect(self.db_path, timeout=15, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA busy_timeout=15000")
        try:
            self._assert_current(con)
            yield con
        finally:
            con.close()

    def _assert_current(self, con):
        exists = con.execute("SELECT 1 FROM sqlite_master WHERE name='library_location'").fetchone()
        moved = con.execute("SELECT destination FROM library_location LIMIT 1").fetchone() if exists else None
        if moved:
            raise LibraryRelocated(moved[0])

    def _initialize(self):
        with self.connection() as con:
            con.execute("PRAGMA journal_mode=WAL")
            con.executescript("""
                CREATE TABLE IF NOT EXISTS migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS library_location(destination TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS jobs(
                    id TEXT PRIMARY KEY, state TEXT NOT NULL, input TEXT NOT NULL,
                    progress TEXT NOT NULL DEFAULT '{}', error TEXT, approval TEXT,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    lease_owner TEXT, lease_until REAL, heartbeat REAL,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    attempts INTEGER NOT NULL DEFAULT 0, next_run_at REAL NOT NULL DEFAULT 0,
                    generation_id TEXT);
                CREATE INDEX IF NOT EXISTS jobs_queue ON jobs(state,next_run_at,created_at);
                CREATE TABLE IF NOT EXISTS checkpoints(
                    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                    name TEXT NOT NULL, value TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY(job_id,name));
                CREATE TABLE IF NOT EXISTS generations(
                    id TEXT PRIMARY KEY, job_id TEXT NOT NULL UNIQUE REFERENCES jobs(id),
                    source_id TEXT NOT NULL, title TEXT NOT NULL, summary TEXT NOT NULL,
                    language TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,
                    page_path TEXT NOT NULL, metadata TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS generations_source ON generations(source_id,created_at);
            """)
            con.execute("INSERT OR IGNORE INTO migrations VALUES(1,?)", (utcnow(),))
            for key, value in DEFAULT_SETTINGS.items():
                con.execute("INSERT OR IGNORE INTO settings VALUES(?,?)", (key, json_text(value)))

    def settings(self) -> dict:
        with self.connection() as con:
            values = {row["key"]: json.loads(row["value"]) for row in con.execute("SELECT key,value FROM settings")}
        settings = DEFAULT_SETTINGS | values
        for name, connection in settings.get("api_connections", {}).items():
            connection.setdefault("requires_key", name != "selfhost")
        return settings

    def save_settings(self, values: dict) -> dict:
        unknown = set(values) - set(DEFAULT_SETTINGS)
        if unknown:
            raise ValueError("Unknown settings: " + ", ".join(sorted(unknown)))
        with self.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            for key, value in values.items():
                con.execute("INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json_text(value)))
            con.commit()
        return self.settings()

    def _job(self, row) -> dict | None:
        if row is None:
            return None
        item = dict(row)
        for field in ("input", "progress", "error", "approval"):
            if item[field]:
                item[field] = json.loads(item[field])
        item["cancel_requested"] = bool(item["cancel_requested"])
        return item

    def create_job(self, input: dict, *, state: str = "queued") -> dict:
        if state not in {"queued", "awaiting_approval"}:
            raise ValueError("Invalid initial job state")
        job_id = uuid.uuid4().hex
        stamp = utcnow()
        with self.connection() as con:
            con.execute("INSERT INTO jobs(id,state,input,created_at,updated_at) VALUES(?,?,?,?,?)", (job_id, state, json_text(input), stamp, stamp))
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> dict | None:
        with self.connection() as con:
            return self._job(con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())

    def list_jobs(self, limit: int = 100) -> list[dict]:
        with self.connection() as con:
            return [self._job(row) for row in con.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,))]

    def update_job(self, job_id: str, *, expected_owner: str | None = None, **fields) -> dict:
        allowed = {"state", "input", "progress", "error", "approval", "lease_owner", "lease_until", "heartbeat", "cancel_requested", "next_run_at", "generation_id"}
        if set(fields) - allowed:
            raise ValueError("Invalid job fields")
        if "state" in fields and fields["state"] not in VALID_STATES:
            raise ValueError("Invalid job state")
        for key in ("input", "progress", "error", "approval"):
            if key in fields and fields[key] is not None:
                fields[key] = json_text(fields[key])
        fields["updated_at"] = utcnow()
        with self.connection() as con:
            clause = " WHERE id=?" + (" AND lease_owner=?" if expected_owner else "")
            parameters = (*fields.values(), job_id, expected_owner) if expected_owner else (*fields.values(), job_id)
            result = con.execute("UPDATE jobs SET " + ",".join(key + "=?" for key in fields) + clause, parameters)
            if not result.rowcount:
                if expected_owner:
                    raise InterruptedError("This worker no longer owns the job")
                raise KeyError(job_id)
        return self.get_job(job_id)

    def claim_job(self, owner: str, lease_seconds: int = 60) -> dict | None:
        now = time.time()
        with self.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            self._assert_current(con)
            # An expired lease means an interrupted worker. Its checkpoints remain available.
            placeholders = ",".join("?" for _ in ACTIVE_STATES)
            con.execute("UPDATE jobs SET state='queued',lease_owner=NULL,lease_until=NULL WHERE state IN (" + placeholders + ") AND (lease_until IS NULL OR lease_until<?)", (*ACTIVE_STATES, now))
            con.execute("UPDATE jobs SET state='cancelled',lease_owner=NULL,lease_until=NULL,updated_at=? WHERE cancel_requested=1 AND state IN ('queued','waiting_for_quota')", (utcnow(),))
            # All worker processes share this gate. V1 has one active job, even
            # when the owner accidentally starts a second worker.
            if con.execute("SELECT 1 FROM jobs WHERE state IN (" + placeholders + ") AND lease_until>=? LIMIT 1", (*ACTIVE_STATES, now)).fetchone():
                con.commit()
                return None
            row = con.execute("SELECT id FROM jobs WHERE state IN ('queued','waiting_for_quota') AND next_run_at<=? AND cancel_requested=0 AND (lease_until IS NULL OR lease_until<?) ORDER BY created_at LIMIT 1", (now, now)).fetchone()
            if row is None:
                con.commit()
                return None
            con.execute("UPDATE jobs SET state='retrieving',lease_owner=?,lease_until=?,heartbeat=?,attempts=attempts+1,updated_at=? WHERE id=?", (owner, now + lease_seconds, now, utcnow(), row["id"]))
            con.commit()
        return self.get_job(row["id"])

    def heartbeat(self, job_id: str, owner: str, lease_seconds: int = 60) -> bool:
        now = time.time()
        with self.connection() as con:
            result = con.execute("UPDATE jobs SET heartbeat=?,lease_until=? WHERE id=? AND lease_owner=? AND state NOT IN ('complete','failed','cancelled','awaiting_approval','waiting_for_quota')", (now, now + lease_seconds, job_id, owner))
        return bool(result.rowcount)

    def release(self, job_id: str, owner: str):
        with self.connection() as con:
            con.execute("UPDATE jobs SET lease_owner=NULL,lease_until=NULL WHERE id=? AND lease_owner=?", (job_id, owner))

    def cancel(self, job_id: str) -> dict:
        job = self.get_job(job_id)
        if not job:
            raise KeyError(job_id)
        if job["state"] == "complete":
            raise ValueError("A saved page cannot be cancelled. Delete it from the library instead.")
        immediate = job["state"] not in ACTIVE_STATES
        return self.update_job(job_id, cancel_requested=True, **({"state": "cancelled"} if immediate else {}))

    def checkpoint(self, job_id: str, name: str, value: dict, *, expected_owner: str | None = None):
        if not SAFE_NAME.fullmatch(name):
            raise ValueError("Invalid checkpoint name")
        with self.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            if expected_owner and not con.execute("SELECT 1 FROM jobs WHERE id=? AND lease_owner=? AND cancel_requested=0", (job_id, expected_owner)).fetchone():
                con.rollback()
                raise InterruptedError("This worker no longer owns the job")
            con.execute("INSERT INTO checkpoints VALUES(?,?,?,?) ON CONFLICT(job_id,name) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at", (job_id, name, json_text(value), utcnow()))
            con.commit()

    def load_checkpoint(self, job_id: str, name: str):
        with self.connection() as con:
            row = con.execute("SELECT value FROM checkpoints WHERE job_id=? AND name=?", (job_id, name)).fetchone()
        return json.loads(row["value"]) if row else None

    def clear_checkpoints(self, job_id: str, preserve: tuple[str, ...] = ("source",)):
        with self.connection() as con:
            if preserve:
                con.execute("DELETE FROM checkpoints WHERE job_id=? AND name NOT IN (" + ",".join("?" for _ in preserve) + ")", (job_id, *preserve))
            else:
                con.execute("DELETE FROM checkpoints WHERE job_id=?", (job_id,))

    def artifact_dir(self, job_id: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{32}", job_id):
            raise ValueError("Invalid job ID")
        result = self.root / "jobs" / job_id
        result.mkdir(parents=True, exist_ok=True)
        return result

    def atomic_write(self, path: Path, content: bytes):
        path = self.managed_path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(prefix=".writing-", dir=path.parent)
        try:
            with os.fdopen(handle, "wb") as file:
                file.write(content)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def write_json(self, job_id: str, name: str, data) -> Path:
        if not SAFE_NAME.fullmatch(name):
            raise ValueError("Invalid artifact name")
        path = self.artifact_dir(job_id) / name
        self.atomic_write(path, json_text(data).encode("utf-8"))
        return path

    def managed_path(self, path: Path | str) -> Path:
        value = Path(path)
        if not value.is_absolute():
            value = self.root / value
        value = value.resolve()
        if not value.is_relative_to(self.root):
            raise ValueError("Artifact path is outside managed storage")
        return value

    def publish_generation(self, job_id: str, result: dict, *, expected_owner: str | None = None) -> dict:
        page = self.managed_path(result["page_path"])
        if not page.is_file() or page.stat().st_size == 0:
            raise ValueError("The learning page is missing or empty")
        job = self.get_job(job_id)
        generation_id = uuid.uuid4().hex
        preferences = job["input"]["preferences"]
        metadata = {key: str(value) if isinstance(value, Path) else value for key, value in result.items() if key != "page_path"}
        from .provider_config import provider_label
        metadata["provider_name"] = provider_label(preferences, preferences.get("provider", "codex"))
        with self.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            current = con.execute("SELECT state,cancel_requested,generation_id,lease_owner FROM jobs WHERE id=?", (job_id,)).fetchone()
            if current["cancel_requested"] or (expected_owner and current["lease_owner"] != expected_owner):
                con.rollback()
                raise InterruptedError("Processing was cancelled or another worker resumed it")
            if current["generation_id"]:
                con.rollback()
                return self.get_generation(current["generation_id"])
            con.execute("INSERT INTO generations VALUES(?,?,?,?,?,?,?,?,?,?,?)", (generation_id, job_id, result.get("source_id", job["input"].get("video_id", job_id)), str(result.get("title", "Learning page")), str(result.get("summary", "")), preferences.get("language", "vi"), preferences.get("provider", "codex"), preferences.get("model", ""), str(page.relative_to(self.root)), json_text(metadata), utcnow()))
            con.execute("UPDATE jobs SET state='complete',generation_id=?,progress=?,error=NULL,lease_owner=NULL,lease_until=NULL,updated_at=? WHERE id=?", (generation_id, json_text({"stage": "complete", "message": "Your learning page is ready."}), utcnow(), job_id))
            con.commit()
        return self.get_generation(generation_id)

    def _generation(self, row) -> dict | None:
        if row is None:
            return None
        item = dict(row)
        item["metadata"] = json.loads(item["metadata"])
        return item

    def get_generation(self, generation_id: str) -> dict | None:
        with self.connection() as con:
            return self._generation(con.execute("SELECT * FROM generations WHERE id=?", (generation_id,)).fetchone())

    def library(self, query: str = "", language: str = "") -> list[dict]:
        with self.connection() as con:
            rows = con.execute("SELECT * FROM generations WHERE (?='' OR language=?) AND (?='' OR title LIKE ? OR summary LIKE ?) ORDER BY created_at DESC", (language, language, query, "%" + query + "%", "%" + query + "%"))
            return [self._generation(row) for row in rows]

    def find_existing(self, video_id: str) -> list[dict]:
        with self.connection() as con:
            rows = con.execute("SELECT g.* FROM generations g JOIN jobs j ON j.id=g.job_id WHERE json_extract(j.input,'$.video_id')=? ORDER BY g.created_at DESC", (video_id,))
            return [self._generation(row) for row in rows]

    def delete_generation(self, generation_id: str):
        # Remove this version and its managed source artifacts together.
        with self.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT job_id FROM generations WHERE id=?", (generation_id,)).fetchone()
            if not row:
                raise KeyError(generation_id)
            con.execute("DELETE FROM generations WHERE id=?", (generation_id,))
            con.execute("DELETE FROM jobs WHERE id=?", (row["job_id"],))
            con.commit()
        folder = self.artifact_dir(row["job_id"])
        # Delete only validated managed contents. A symlink outside storage is rejected.
        import shutil
        self.managed_path(folder)
        if folder.exists():
            shutil.rmtree(folder)

    def backup(self) -> Path:
        """Create a consistent SQLite snapshot plus every artifact referenced by it."""
        backups = self.root / "backups"
        backups.mkdir(exist_ok=True)
        target = backups / ("distill-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6] + ".zip")
        with tempfile.TemporaryDirectory(prefix="vl-backup-") as temporary:
            snapshot = Path(temporary) / "library.sqlite3"
            with self.connection() as gate:
                # Keep referenced jobs stable while copying their files. A worker
                # cannot claim a new job until this short backup finishes.
                gate.execute("BEGIN IMMEDIATE")
                running = gate.execute("SELECT state,approval FROM jobs").fetchall()
                if any(row["state"] in ACTIVE_STATES | {"queued"} or (row["state"] == "awaiting_approval" and not row["approval"]) for row in running):
                    gate.rollback()
                    raise ValueError("Wait for processing to finish or cancel it before making a library backup.")
                with self.connection() as source:
                    destination = sqlite3.connect(snapshot)
                    try:
                        source.backup(destination)
                    finally:
                        destination.close()
                job_ids = [row[0] for row in gate.execute("SELECT id FROM jobs")]
                with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                    archive.write(snapshot, "library.sqlite3")
                    archive.writestr("BACKUP_README.txt", "Distill backup. Stop the app and worker before restoring library.sqlite3 and jobs/ into an empty data folder. API keys are not included.\n")
                    for job_id in job_ids:
                        folder = self.artifact_dir(job_id)
                        for artifact in folder.rglob("*"):
                            if artifact.is_file() and not artifact.name.startswith(".writing-"):
                                self.managed_path(artifact)
                                archive.write(artifact, str(artifact.relative_to(self.root)))
                gate.commit()
        return target

    def storage_info(self) -> dict:
        total = sum(file.stat().st_size for file in self.root.rglob("*") if file.is_file())
        return {"path": str(self.root), "size_bytes": total, "database": "SQLite (no separate server)"}

    def relocate(self, requested: str) -> "Store":
        """Copy a stable library, retain the original, then switch its locator."""
        raw = requested.strip()
        if not raw or not Path(raw).expanduser().is_absolute():
            raise ValueError("Enter a full folder path, such as D:\\MyLearningLibrary.")
        if os.name == "nt":
            from pathlib import PureWindowsPath
            windows = PureWindowsPath(raw)
            if raw.startswith(("\\\\", "//")) or any(char in raw[2:] for char in '<>:"|?*') or any(part.endswith((".", " ")) or (os.path.isreserved(part) if hasattr(os.path, "isreserved") else PureWindowsPath(part).is_reserved()) for part in windows.parts[1:]):
                raise ValueError("Choose a valid local Windows folder path.")
        target = Path(raw).expanduser().resolve()
        if target == self.root:
            remember_data_dir(target)
            return self
        if target.is_relative_to(self.root) or self.root.is_relative_to(target):
            raise ValueError("Choose a separate folder outside the current library.")
        protected = [app_config_dir(), Path.home() / ".codex", Path.home() / ".ssh"]
        if os.environ.get("CODEX_HOME"):
            protected.append(Path(os.environ["CODEX_HOME"]))
        if os.name == "nt":
            protected.extend(Path(os.environ[name]) for name in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramData") if os.environ.get(name))
            protected.extend([Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Microsoft" / "Credentials", Path.home() / "AppData" / "Roaming" / "Microsoft" / "Credentials"])
        if target == Path.home().resolve() or target == Path(target.anchor) or any(target.is_relative_to(folder.resolve()) or folder.resolve().is_relative_to(target) for folder in protected):
            raise ValueError("Choose a dedicated library folder outside system, app configuration, and credential folders.")
        if target.exists() and (not target.is_dir() or any(target.iterdir())):
            raise ValueError("Choose a new or empty folder. Existing files will not be replaced.")
        parent = target.parent
        parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=".distill-copy-", dir=parent))
        published = False
        selection_changed = False
        committed = False
        try:
            with self.connection() as gate:
                gate.execute("BEGIN IMMEDIATE")
                self._assert_current(gate)
                rows = gate.execute("SELECT state,lease_owner,lease_until FROM jobs").fetchall()
                if any(row["state"] in ACTIVE_STATES | {"queued", "waiting_for_quota"} or row["lease_owner"] for row in rows):
                    raise ValueError("Wait for processing to finish, or cancel running and queued jobs before changing the library folder.")
                # The database writer gate also stops external workers from claiming a job.
                for file in self.root.rglob("*"):
                    if file.is_symlink() or (hasattr(file, "is_junction") and file.is_junction()):
                        raise ValueError("The library contains a linked folder or file. Remove the link before changing folders.")
                    if file.is_file() and file.name not in {"library.sqlite3", "library.sqlite3-wal", "library.sqlite3-shm"} and not file.name.startswith(".writing-"):
                        self.managed_path(file)
                        destination = temporary / file.relative_to(self.root)
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(file, destination)
                with self.connection() as source:
                    with closing(sqlite3.connect(temporary / "library.sqlite3")) as destination:
                        source.backup(destination)
                original_snapshot = self.root / ("library-before-move-" + uuid.uuid4().hex[:8] + ".sqlite3")
                shutil.copy2(temporary / "library.sqlite3", original_snapshot)
                self.atomic_write(self.root / "LIBRARY_MOVED.txt", ("Original library backup. To restore this copy, stop the app and worker, copy " + original_snapshot.name + " plus jobs/ into a new empty folder, rename the copied database library.sqlite3, then start with --data-dir pointing to that folder. The active library is now " + str(target) + ". API keys are stored separately.\n").encode("utf-8"))
                # Imported audio and cached generation records can contain absolute paths.
                def rewrite(value):
                    if isinstance(value, dict):
                        return {key: rewrite(item) for key, item in value.items()}
                    if isinstance(value, list):
                        return [rewrite(item) for item in value]
                    if isinstance(value, str):
                        old = str(self.root)
                        if value == old or value.startswith(old + os.sep):
                            return str(target) + value[len(old):]
                    return value
                with closing(sqlite3.connect(temporary / "library.sqlite3")) as destination, destination:
                    for table, columns, key in (("jobs", ("input", "approval"), "id"), ("checkpoints", ("value",), "rowid"), ("generations", ("metadata",), "id")):
                        for row in destination.execute("SELECT " + key + "," + ",".join(columns) + " FROM " + table).fetchall():
                            for index, column in enumerate(columns, 1):
                                if row[index]:
                                    destination.execute("UPDATE " + table + " SET " + column + "=? WHERE " + key + "=?", (json_text(rewrite(json.loads(row[index]))), row[0]))
                    if destination.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise ValueError("The copied library did not pass its integrity check.")
                # Rewrite saved JSON records too; standalone HTML remains byte-for-byte.
                for file in (temporary / "jobs").rglob("*.json"):
                    file.write_text(json_text(rewrite(json.loads(file.read_text(encoding="utf-8")))), encoding="utf-8")
                if target.exists():
                    target.rmdir()  # Only the validated empty destination.
                temporary.rename(target)
                published = True
                gate.execute("INSERT INTO library_location VALUES(?)", (str(target),))
                # Persist outside both libraries. A crash leaves complete copies.
                remember_data_dir(target)
                selection_changed = True
                gate.commit()
                committed = True
            return Store(target)
        except BaseException:
            if selection_changed and not committed:
                remember_data_dir(self.root)
            # Keep a published copy on failure so source data cannot be lost.
            if not published and temporary.exists():
                shutil.rmtree(temporary)
            raise

    def cleanup_audio(self, older_than_seconds: float = 86400) -> int:
        """Remove temporary audio 24 hours after an inactive failure or cancellation."""
        cutoff = time.time() - older_than_seconds
        removed = 0
        with self.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            self._assert_current(con)
            for row in con.execute("SELECT id,input,updated_at FROM jobs WHERE state IN ('failed','cancelled') AND lease_owner IS NULL"):
                preferences = json.loads(row["input"]).get("preferences", {})
                if preferences.get("retain_audio") or datetime.fromisoformat(row["updated_at"]).timestamp() > cutoff:
                    continue
                folder = self.artifact_dir(row["id"])
                for pattern in ("imported-audio.*", "source-audio.*", "chunks/*.wav", "chunks/*.flac", "chunks/*.partial.wav"):
                    for path in folder.glob(pattern):
                        path = self.managed_path(path)
                        if path.is_file() and path.stat().st_mtime < cutoff:
                            path.unlink()
                            removed += 1
            con.commit()
        return removed
