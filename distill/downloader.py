"""yt-dlp, the YouTube downloader: one command line, readable errors, and a way to keep it current.

YouTube changes often and an old yt-dlp is the usual reason a download breaks, so the app reports
its version, can install the latest release into its own environment, and names that fix in errors.
"""
from __future__ import annotations

import importlib.metadata
import json
import re
import shutil
import subprocess
import sys

import requests

PYPI_URL = "https://pypi.org/pypi/yt-dlp/json"
# Error lines name the cause; URLs keep their path but lose the query, which can hold signed tokens.
_QUERY = re.compile(r"(https?://[^\s?]+)\?\S*")
PATTERNS = [
    (r"confirm your age|age[- ]restricted|inappropriate for some users", "inaccessible",
     "This video is age-restricted and needs a signed-in account. Import a transcript or the audio file instead."),
    (r"confirm you.?re not a bot|confirm you are not a bot", "blocked",
     "YouTube asked to confirm that this is not a bot. Wait and retry later, or import a transcript or the audio file."),
    (r"private video|video unavailable|has been removed|account associated with this video has been terminated|not available in your country",
     "inaccessible", "This video is private, removed or not available here."),
    (r"live event will begin|premieres in|this live event|is not yet available", "inaccessible",
     "This live stream or premiere has not started or ended yet. Retry after it ends."),
    (r"HTTP Error 403|403: Forbidden", "downloader_outdated",
     "YouTube refused the download (HTTP 403). Update yt-dlp in Settings, then retry."),
    (r"requested format is not available|nsig extraction failed|n challenge solving failed|signature extraction failed|"
     r"only images are available|unable to extract|unsupported url", "downloader_outdated",
     "yt-dlp could not read this video. Update yt-dlp in Settings, then retry."),
    (r"timed out|connection reset|getaddrinfo|temporary failure in name resolution|unable to download webpage|network is unreachable",
     "temporary", "YouTube could not be reached. Retry later."),
]


class DownloadError(RuntimeError):
    def __init__(self, code: str, message: str, diagnostics: dict | None = None):
        super().__init__(message)
        self.code, self.message, self.diagnostics = code, message, diagnostics or {}


def error_lines(stderr: str, limit: int = 6) -> list[str]:
    """The last meaningful lines of a tool's error output, shortened and without URL queries."""
    lines = [line.strip() for line in (stderr or "").splitlines()]
    lines = [_QUERY.sub(r"\1?…", line)[:240] for line in lines if line and not line.startswith("[debug]")]
    return lines[-limit:]


def classify(stderr: str) -> tuple[str, str] | None:
    """A known cause and its message, or None when the output names no known cause."""
    text = (stderr or "").lower()
    for pattern, code, message in PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return code, message
    return None


def command(*arguments: str) -> list[str]:
    """yt-dlp from the app's own environment. Without Deno, Node solves YouTube's JavaScript challenge."""
    base = [sys.executable, "-m", "yt_dlp", "--no-playlist"]
    node = shutil.which("node")
    if not shutil.which("deno") and node:
        base += ["--js-runtimes", f"node:{node}"]
    return base + list(arguments)


def video_info(video_id: str, timeout: float = 90) -> dict:
    """yt-dlp's description of a video without downloading it: language, captions, title, duration."""
    try:
        done = subprocess.run(command("-J", "--skip-download", "--no-warnings", "--", f"https://www.youtube.com/watch?v={video_id}"),
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                              creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    except subprocess.TimeoutExpired as exc:
        raise DownloadError("temporary", "yt-dlp took too long to read this video. Retry later.") from exc
    except OSError as exc:
        raise DownloadError("missing_dependency", "yt-dlp could not start. Reinstall the app requirements.") from exc
    if done.returncode != 0:
        known = classify(done.stderr)
        code, message = known or ("downloader_failed", "yt-dlp could not read this video.")
        raise DownloadError(code, message, {"tool": "yt-dlp", "exit_code": done.returncode, "error_lines": error_lines(done.stderr)})
    try:
        return json.loads(done.stdout)
    except json.JSONDecodeError as exc:
        raise DownloadError("downloader_failed", "yt-dlp returned no video description.") from exc


def caption_track(info: dict, language: str | None) -> tuple[str, str, dict] | None:
    """(track, kind, json3 format) for the spoken language, best first.

    Kind is "manual" or "generated". Order: uploaded subtitles in that language, then the automatic
    captions of the original audio (`<lang>-orig`), then plain automatic captions in that language.
    Translations into other languages are never chosen here.
    """
    wanted = (language or info.get("language") or "").split("-")[0].lower()
    if not wanted:
        return None
    subtitles, automatic = info.get("subtitles") or {}, info.get("automatic_captions") or {}
    base = lambda key: key.split("-")[0].lower()
    choices = [(subtitles, "manual", lambda key: base(key) == wanted and not key.endswith("-orig")),
               (automatic, "generated", lambda key: base(key) == wanted and key.endswith("-orig")),
               (automatic, "generated", lambda key: key.lower() == wanted)]
    for tracks, kind, matches in choices:
        for key in sorted(tracks, key=lambda key: (key.lower() != wanted, key)):
            formats = tracks[key] or []
            json3 = next((item for item in formats if item.get("ext") == "json3" and item.get("url")), None)
            if matches(key) and json3:
                return key, kind, json3
    return None


def json3_snippets(data: dict) -> list[dict]:
    """YouTube's json3 caption events as timed snippets."""
    snippets = []
    for event in data.get("events") or []:
        text = "".join(segment.get("utf8", "") for segment in event.get("segs") or []).replace("\n", " ")
        text = " ".join(text.split())
        if not text:
            continue
        start = (event.get("tStartMs") or 0) / 1000
        duration = (event.get("dDurationMs") or 0) / 1000
        snippets.append({"id": f"s{len(snippets) + 1:06d}", "text": text, "start": start, "end": start + duration,
                         "duration": duration, "timing_basis": "caption"})
    return snippets


def installed_version() -> str | None:
    try:
        return importlib.metadata.version("yt-dlp")
    except importlib.metadata.PackageNotFoundError:
        return None


def latest_version(timeout: float = 10) -> str:
    response = requests.get(PYPI_URL, timeout=timeout)
    response.raise_for_status()
    return response.json()["info"]["version"]


def status(check_latest: bool = False) -> dict:
    """What the Settings view shows: the installed release, the newest one when asked, the JavaScript runtime."""
    result = {"installed": installed_version(), "latest": None, "update_available": None,
              "javascript_runtime": "deno" if shutil.which("deno") else "node" if shutil.which("node") else None}
    if check_latest:
        try:
            result["latest"] = latest_version()
        except (requests.RequestException, KeyError, ValueError):
            result["latest_error"] = "The newest release could not be checked. Check the internet connection."
        else:
            result["update_available"] = _release(result["latest"]) > _release(result["installed"])
    return result


def _release(version: str | None) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", version or "0"))


def update(timeout: float = 600) -> dict:
    """Install the newest yt-dlp, with its default extras (the JavaScript challenge solver), into the app's environment."""
    before = installed_version()
    try:
        done = subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "--disable-pip-version-check", "yt-dlp[default]"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                              creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    except subprocess.TimeoutExpired as exc:
        raise DownloadError("timeout", "The yt-dlp update took too long. Check the internet connection and retry.") from exc
    if done.returncode != 0:
        raise DownloadError("update_failed", "yt-dlp could not be updated.", {"exit_code": done.returncode, "error_lines": error_lines(done.stderr or done.stdout)})
    return {"previous": before, "installed": installed_version()}
