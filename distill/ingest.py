"""Retrieve captions and recover from blocked sources through file imports."""
from __future__ import annotations

import html
import json
import math
from pathlib import Path
import re
from urllib.parse import parse_qs, urlparse
import uuid

import requests

from .models import Transcript


class CaptionError(RuntimeError):
    def __init__(self, code: str, message: str, languages=None, retry_after=None):
        super().__init__(message)
        self.code, self.languages, self.retry_after = code, languages or [], retry_after


def parse_youtube_id(value: str) -> str:
    if not isinstance(value, str):
        raise CaptionError("invalid_url", "Enter a valid YouTube video link.")
    value = value.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
        return value
    try:
        parsed = urlparse(value if "://" in value else "https://" + value)
        host = (parsed.hostname or "").lower()
        port = parsed.port
    except ValueError as exc:
        raise CaptionError("invalid_url", "Enter a valid YouTube video link.") from exc
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password or port not in {None, 80, 443}:
        raise CaptionError("invalid_url", "Enter a valid YouTube video link.")
    if host == "youtu.be":
        candidate = parsed.path.strip("/")
    elif host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
        if parsed.path == "/watch":
            candidate = parse_qs(parsed.query).get("v", [""])[0]
        else:
            match = re.fullmatch(r"/(?:shorts|embed|live)/([A-Za-z0-9_-]{11})/?", parsed.path)
            candidate = match.group(1) if match else ""
    else:
        candidate = ""
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate):
        raise CaptionError("invalid_url", "Enter a YouTube watch, short, or shared video link.")
    return candidate


class _TimeoutSession(requests.Session):
    def request(self, *args, **kwargs):
        kwargs.setdefault("timeout", (10, 30))
        return super().request(*args, **kwargs)


def fetch_youtube(video_id: str, source_language: str | None = None) -> Transcript:
    video_id = parse_youtube_id(video_id)
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api import _errors as errors
    available = []
    session = _TimeoutSession()
    try:
        listing = list(YouTubeTranscriptApi(http_client=session).list(video_id))
        available = [{"code": t.language_code, "name": t.language, "generated": t.is_generated} for t in listing]
        suitable = listing
        if source_language:
            suitable = [t for t in listing if t.language_code.lower() == source_language.lower()]
            if not suitable:
                suitable = [t for t in listing if t.language_code.split("-")[0].lower() == source_language.split("-")[0].lower()]
            if not suitable:
                raise CaptionError("language_mismatch", "Captions are available in other languages. Choose a listed source language.", available)
        if not suitable:
            raise CaptionError("missing_captions", "YouTube did not provide captions for this video.", available)
        # Keep original captions; never request YouTube's machine translation.
        selected = sorted(suitable, key=lambda t: (t.is_generated, 0 if t.language_code.split("-")[0] in {"en", "vi"} else 1))[0]
        fetched = selected.fetch()
        snippets = [{"id": f"s{index:06d}", "text": s.text, "start": s.start, "end": s.start + s.duration, "duration": s.duration, "timing_basis": "caption"} for index, s in enumerate(fetched, 1) if s.text.strip()]
        title = f"YouTube · {video_id}"
        metadata = {"caption_language_name": selected.language, "available_languages": available, "timing_note": "Caption duration is display time and may overlap, not exact speech duration.", "language_selection": "explicit" if source_language else "automatic", "language_note": "Automatic selection does not verify the original spoken track. Choose the source language if several caption or dubbed tracks exist." if not source_language and len(available) > 1 else ""}
        try:
            response = session.get("https://www.youtube.com/oembed", params={"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"}, timeout=(5, 8))
            if response.ok:
                data = response.json()
                title = data.get("title") or title
                metadata.update({"author": data.get("author_name", ""), "thumbnail_url": data.get("thumbnail_url", "")})
        except (requests.RequestException, ValueError):
            pass
        return Transcript(source_id=video_id, video_id=video_id, url=f"https://www.youtube.com/watch?v={video_id}", title=title, language=selected.language_code, origin="generated_captions" if selected.is_generated else "manual_captions", snippets=snippets, metadata=metadata)
    except CaptionError:
        raise
    except (errors.RequestBlocked, errors.IpBlocked) as exc:
        raise CaptionError("blocked", "YouTube blocked this caption request. This does not mean captions are missing. Import a transcript or approve audio fallback.", available) from exc
    except (errors.TranscriptsDisabled, errors.NoTranscriptFound) as exc:
        raise CaptionError("missing_captions", "Captions could not be found. Import a transcript or approve audio fallback.", available) from exc
    except (errors.VideoUnavailable, errors.VideoUnplayable, errors.AgeRestricted) as exc:
        raise CaptionError("inaccessible", "This video is unavailable or requires access that this app does not have.", available) from exc
    except requests.RequestException as exc:
        raise CaptionError("temporary", "YouTube could not be reached. Retry later or import a transcript.", available, 30) from exc
    except errors.YouTubeTranscriptApiException as exc:
        raise CaptionError("retrieval_failed", "YouTube captions could not be read. Import a transcript or approve audio fallback.", available) from exc
    finally:
        session.close()


def _timestamp(text: str) -> float:
    parts = text.replace(",", ".").split(":")
    if len(parts) not in {2, 3}:
        raise ValueError("Invalid subtitle timestamp")
    seconds = float(parts[-1])
    minutes = int(parts[-2])
    hours = int(parts[-3]) if len(parts) == 3 else 0
    if not 0 <= seconds < 60 or not 0 <= minutes < 60 or hours < 0:
        raise ValueError("Invalid subtitle timestamp")
    return hours * 3600 + minutes * 60 + seconds


def _subtitle_snippets(text: str) -> list[dict]:
    snippets = []
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if re.match(r"^(NOTE(?:\s|$)|STYLE$|REGION$)", line):
            while index < len(lines) and lines[index].strip():
                index += 1
            continue
        if "-->" not in line:
            index += 1
            continue
        times = line.split("-->", 1)
        start, end = _timestamp(times[0].strip()), _timestamp(times[1].strip().split()[0])
        index += 1
        contents = []
        while index < len(lines) and lines[index].strip():
            contents.append(lines[index].strip())
            index += 1
        content = " ".join(contents)
        speaker_match = re.search(r"<v\s+([^>]+)>", content)
        content = html.unescape(re.sub(r"<[^>]+>", "", content)).strip()
        if content:
            snippets.append({"id": f"s{len(snippets)+1:06d}", "text": content, "start": start, "end": end, "duration": end-start, "timing_basis": "caption", "speaker": speaker_match.group(1) if speaker_match else None})
    return snippets


def _validated_import(transcript: Transcript) -> Transcript:
    for snippet in transcript.snippets:
        if any(value is not None and not math.isfinite(value) for value in (snippet.start, snippet.end, snippet.duration)):
            raise ValueError("Non-finite transcript timestamp")
    if transcript.video_id:
        transcript.url = f"https://www.youtube.com/watch?v={transcript.video_id}"
    elif transcript.url:
        parsed = urlparse(transcript.url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Invalid source URL")
    return transcript


def parse_import(data: bytes | str, filename: str, metadata: dict | None = None) -> Transcript:
    meta = dict(metadata or {})
    try:
        text = data.decode("utf-8-sig") if isinstance(data, bytes) else data.lstrip("\ufeff")
    except UnicodeDecodeError as exc:
        raise CaptionError("invalid_import", "Save this transcript as UTF-8 and import it again.") from exc
    if not text.strip():
        raise CaptionError("invalid_import", "This file contains no transcript text.")
    extension = Path(filename).suffix.lower()
    video_id = parse_youtube_id(meta["video_id"]) if meta.get("video_id") else (parse_youtube_id(meta["url"]) if meta.get("url") else None)
    source_id = video_id or "import-" + uuid.uuid4().hex
    try:
        if extension == ".json":
            body = json.loads(text)
            if isinstance(body, dict) and body.get("video_id") and video_id:
                if parse_youtube_id(str(body["video_id"])) != video_id:
                    raise ValueError("Imported transcript belongs to a different video")
            if isinstance(body, dict) and "source_id" in body and "snippets" in body:
                imported = Transcript.model_validate(body)
                if video_id:
                    imported.video_id = video_id
                    imported.source_id = video_id
                    imported.url = f"https://www.youtube.com/watch?v={video_id}"
                return _validated_import(imported)
            if isinstance(body, dict):
                rows = body.get("snippets", body.get("segments", body.get("transcript", [])))
                for key in ["title", "language", "video_id"]:
                    if key in body and key not in meta: meta[key] = body[key]
                if body.get("video_id") and not video_id:
                    video_id = parse_youtube_id(str(body["video_id"]))
                    source_id = video_id
            else:
                rows = body
            if not isinstance(rows, list): raise ValueError("JSON needs transcript segments")
            snippets = []
            for i, row in enumerate(rows, 1):
                if not isinstance(row, dict) or not isinstance(row.get("text"), str): raise ValueError("Invalid transcript segment")
                if not row["text"].strip(): continue
                start = row.get("start")
                duration = row.get("duration")
                end = row.get("end")
                if end is None and start is not None and duration is not None: end = float(start)+float(duration)
                snippets.append({"id": row.get("id", f"s{i:06d}"), "text": row["text"], "start": start, "end": end, "duration": duration, "speaker": row.get("speaker"), "timing_basis": row.get("timing_basis", "caption" if start is not None else "unknown")})
        elif extension in {".srt", ".vtt"}:
            snippets = _subtitle_snippets(text)
        elif extension == ".txt":
            paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
            snippets = [{"id": f"s{i:06d}", "text": paragraph, "timing_basis": "unknown"} for i, paragraph in enumerate(paragraphs, 1)]
            meta["timing_note"] = "Plain text has no verified timestamps."
        else:
            raise ValueError("Unsupported file type")
        meta["filename"] = Path(filename).name
        return _validated_import(Transcript(source_id=source_id, video_id=video_id, url=f"https://www.youtube.com/watch?v={video_id}" if video_id else None, title=meta.get("title") or Path(filename).stem, language=meta.get("language") or "unknown", origin="import", snippets=snippets, metadata=meta))
    except (ValueError, TypeError, KeyError) as exc:
        raise CaptionError("invalid_import", "This transcript format is invalid. Use TXT, SRT, VTT, or transcript JSON with text and optional timestamps.") from exc
