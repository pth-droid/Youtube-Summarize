"""Local application settings. Credentials are deliberately not stored here."""

from __future__ import annotations

import os
import json
import tempfile
from pathlib import Path

APP_NAME = "Visual Learning"
DEFAULT_PORT = 8765
MAX_IMPORT_BYTES = 20 * 1024 * 1024
MAX_AUDIO_BYTES = 1024 * 1024 * 1024

DEFAULT_SETTINGS = {
    "provider": "codex",
    "language": "vi",
    "output_language": "vi",
    "source_language": "",
    "knowledge_level": "balanced",
    "learning_goal": "",
    "codex_model": "",
    "claude_code_model": "",
    "deepseek_model": "deepseek-flash",
    "api_connections": {},
    "groq_model": "whisper-large-v3-turbo",
    "groq_free_only": True,
    "allow_paid_llm": False,
    "retain_audio": False,
}


def app_config_dir() -> Path:
    """Keep the library selection outside the library that can be moved."""
    override = os.environ.get("VISUAL_LEARNING_CONFIG_DIR")
    if override:
        return Path(override).expanduser().resolve()
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) if os.name == "nt" else Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return (base / "VisualLearningConfig").resolve()


def remember_data_dir(folder: Path):
    directory = app_config_dir()
    directory.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix=".library-", dir=directory)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump({"library_folder": str(folder)}, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, directory / "library-location.json")
    finally:
        if os.path.exists(name):
            os.unlink(name)


def default_data_dir() -> Path:
    configured = os.environ.get("VISUAL_LEARNING_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    selection = app_config_dir() / "library-location.json"
    if selection.is_file():
        try:
            folder = json.loads(selection.read_text(encoding="utf-8"))["library_folder"]
            if not isinstance(folder, str) or not Path(folder).is_absolute():
                raise ValueError()
            selected = Path(folder).resolve()
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise ValueError("The saved library location cannot be read. Fix library-location.json or start with --data-dir.") from error
        if not (selected / "library.sqlite3").is_file():
            raise ValueError("The selected library is unavailable. Reconnect its drive or restore its folder before starting.")
        return selected
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
    return (base / "VisualLearning").resolve()
