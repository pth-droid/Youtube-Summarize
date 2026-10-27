"""Approved audio download, timestamp-preserving preparation, and Groq STT."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

import requests

from .ingest import parse_youtube_id
from .models import Transcript
from .providers import ProviderError, SecretStore, http_error, stop_process


SUPPORTED_MODELS = {"whisper-large-v3-turbo", "whisper-large-v3"}
MAX_UPLOAD_BYTES = 24_000_000
MAX_AUDIO_DURATION_SECONDS = 6 * 3600
# Imported content must not make FFmpeg fetch a playlist or external URLs.
MEDIA_INPUT_LIMITS = ["-protocol_whitelist", "file,pipe", "-format_whitelist", "wav,mp3,mov,ogg,matroska,webm,flac,aac"]


def validate_approval(approval: dict, source: str, model: str) -> None:
    if approval.get("approved") is not True or not approval.get("job_id") or approval.get("source") != source or approval.get("provider") != "groq" or approval.get("model") != model:
        raise ProviderError("audio_approval", "Approve this source, Groq model, and audio upload before audio processing.")
    if model not in SUPPORTED_MODELS:
        raise ProviderError("configuration", "Choose a supported Groq Whisper transcription model.")
    if approval.get("free_only", True) and approval.get("free_account_confirmed") is not True:
        raise ProviderError("free_tier_unverified", "Confirm in Groq that this API key belongs to a Free account with no paid billing. The app cannot enforce free billing on a paid account.")
    if not approval.get("free_only", True) and not any(approval.get(key) is True for key in ("paid_approved", "paid_usage_approved")):
        raise ProviderError("paid_approval", "Approve paid Groq usage explicitly before processing audio.")


@dataclass
class AudioChunk:
    index: int
    path: str
    offset: float
    duration: float
    core_start: float
    core_end: float


def plan_chunks(duration: float, seconds: float = 600, overlap: float = 3) -> list[dict]:
    if not all(math.isfinite(value) for value in (duration, seconds, overlap)) or duration <= 0 or seconds <= 2 * overlap or overlap < 0:
        raise ValueError("Invalid audio duration or chunk size")
    chunks = []
    start = 0.0
    while start < duration:
        end = min(start + seconds, duration)
        offset = max(0.0, start - overlap)
        stop = min(duration, end + overlap)
        chunks.append({"index": len(chunks), "offset": offset, "duration": stop - offset, "core_start": start, "core_end": end})
        start = end
    return chunks


def _run(command: list[str], cancelled=None, timeout: float = 900) -> bytes:
    if cancelled and cancelled():
        raise ProviderError("cancelled", "Audio processing was cancelled.")
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    except OSError as exc:
        raise ProviderError("missing_dependency", "The audio preparation command could not start. Check yt-dlp and FFmpeg installation.") from exc
    deadline = time.monotonic() + timeout
    try:
        while True:
            if cancelled and cancelled():
                raise ProviderError("cancelled", "Audio processing was cancelled.")
            if time.monotonic() > deadline:
                raise ProviderError("timeout", "Audio preparation took too long. Retry or import a transcript.")
            try:
                output, _ = process.communicate(timeout=0.2)
                break
            except subprocess.TimeoutExpired:
                continue
        if process.returncode:
            raise ProviderError("audio_failed", "Audio could not be downloaded or prepared. Import an audio file or transcript instead.")
        return output
    finally:
        stop_process(process)


def _binary(name: str) -> str:
    executable = shutil.which(name)
    if not executable:
        raise ProviderError("missing_dependency", f"Install {name} to prepare audio transcription.")
    return executable


def _atomic_json(path: Path, value: dict):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _audio_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1_048_576), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare_chunks(audio_path: Path, work_dir: Path, cancelled=None) -> list[AudioChunk]:
    output = _run([_binary("ffprobe"), "-v", "error", *MEDIA_INPUT_LIMITS, "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)], cancelled, 30)
    try: duration = float(output.decode("utf-8").strip())
    except ValueError as exc: raise ProviderError("audio_failed", "This file has no readable audio duration.") from exc
    if not math.isfinite(duration) or duration <= 0:
        raise ProviderError("audio_failed", "This file has no valid audio duration.")
    if duration > MAX_AUDIO_DURATION_SECONDS:
        raise ProviderError("audio_duration_limit", "Audio is limited to six hours per source. Import shorter sections or a transcript.")
    chunk_dir = work_dir / "chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    chunks = []
    for item in plan_chunks(duration):
        path = chunk_dir / f"chunk-{item['index']:05d}.wav"
        if not path.is_file():
            temporary = path.with_suffix(".partial.wav")
            _run([_binary("ffmpeg"), "-nostdin", "-v", "error", "-y", "-ss", str(item["offset"]), *MEDIA_INPUT_LIMITS, "-i", str(audio_path), "-t", str(item["duration"]), "-map", "0:a:0", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(temporary)], cancelled)
            temporary.replace(path)
        if path.stat().st_size > MAX_UPLOAD_BYTES:
            raise ProviderError("upload_limit", "An audio section exceeds the safe upload limit. Use a smaller imported audio section.")
        chunks.append(AudioChunk(path=str(path), **item))
    return chunks


def merge_chunks(chunks: list[AudioChunk], responses: list[dict]) -> tuple[list[dict], list[str]]:
    """Restore video offsets; deduplicate overlap only, retaining later repeats."""
    snippets, warnings = [], []
    if len(chunks) != len(responses):
        raise ValueError("Each audio chunk needs its own saved response")
    for chunk, response in zip(chunks, responses):
        _validate_response(response, chunk)
        if not response.get("segments"):
            warnings.append(f"No speech segments in audio section {chunk.index+1}; inspect the source if speech was expected.")
        for row in response.get("segments", []):
            text = str(row.get("text", "")).strip()
            try:
                local_start, local_end = float(row["start"]), float(row["end"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ProviderError("invalid_output", "Groq returned a segment without valid timestamps.") from exc
            if not text or not all(math.isfinite(t) for t in (local_start, local_end)) or local_start < 0 or local_end < local_start or local_end > chunk.duration + 1:
                raise ProviderError("invalid_output", "Groq returned invalid audio segment text or timing.")
            start, end = chunk.offset + local_start, chunk.offset + local_end
            if start >= chunk.core_end + 3:
                continue
            normalized = " ".join(text.casefold().split())
            duplicate = False
            for previous in reversed(snippets[-8:]):
                overlap = min(end, previous["end"]) - max(start, previous["start"])
                if previous["_chunk"] != chunk.index and overlap > 0 and SequenceMatcher(None, normalized, " ".join(previous["text"].casefold().split())).ratio() > 0.88:
                    duplicate = True
                    break
            if duplicate:
                continue
            # Keep unmatched content even inside overlap; record partial ambiguity.
            if snippets and start < snippets[-1]["end"] and snippets[-1]["_chunk"] != chunk.index:
                prior = snippets[-1]
                left, right = prior["text"].split(), text.split()
                trim = 0
                for count in range(min(len(left), len(right)), 1, -1):
                    if [w.casefold().strip(".,!?:;") for w in left[-count:]] == [w.casefold().strip(".,!?:;") for w in right[:count]]:
                        trim = count
                        break
                if trim:
                    text = " ".join(right[trim:])
                    if not text: continue
                    # The exact boundary words are unknown; do not invent times.
                    warnings.append(f"Overlap trimmed near {start:.1f}s; segment start is approximate.")
            if float(row.get("no_speech_prob", 0)) > 0.6 or float(row.get("avg_logprob", 0)) < -1:
                warnings.append(f"Uncertain transcription near {start:.1f}s; compare with original audio.")
            snippets.append({"id": "", "text": text, "start": start, "end": end, "duration": end-start, "timing_basis": "speech", "_chunk": chunk.index})
    snippets.sort(key=lambda row: (row["start"], row["end"]))
    for index, row in enumerate(snippets, 1):
        row["id"] = f"s{index:06d}"
        row.pop("_chunk", None)
    if not snippets:
        raise ProviderError("audio_failed", "No speech could be transcribed. Import a transcript or try a different source.")
    return snippets, list(dict.fromkeys(warnings))


def _validate_response(response: dict, chunk: AudioChunk) -> None:
    """Do not cache malformed STT output; an empty segment list means silence."""
    if not isinstance(response, dict) or not isinstance(response.get("segments"), list):
        raise ProviderError("invalid_output", "Groq did not return segment timestamps.")
    if "language" in response and not isinstance(response["language"], str):
        raise ProviderError("invalid_output", "Groq returned an invalid source language.")
    for row in response["segments"]:
        try:
            if not isinstance(row, dict) or not isinstance(row.get("text"), str) or not row["text"].strip():
                raise ValueError("Invalid text")
            start, end = float(row["start"]), float(row["end"])
            scores = [float(row.get(name, 0)) for name in ("no_speech_prob", "avg_logprob")]
            if not all(math.isfinite(value) for value in (start, end, *scores)) or start < 0 or end < start or end > chunk.duration + 1:
                raise ValueError("Invalid timestamp")
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderError("invalid_output", "Groq returned invalid audio segment text or timing.") from exc


def transcribe_audio(audio_path: Path, work_dir: Path, approval: dict, source: str, progress=None, cancelled=None, checkpoint=None, load_checkpoint=None, language: str | None = None, secret_store: SecretStore | None = None) -> Transcript:
    model = approval.get("model", "whisper-large-v3-turbo")
    validate_approval(approval, source, model)
    if cancelled and cancelled():
        raise ProviderError("cancelled", "Audio processing was cancelled.")
    key = (secret_store or SecretStore()).get("groq")
    if not key:
        raise ProviderError("authentication", "Configure a Groq API key before audio transcription.")
    audio_path, work_dir = Path(audio_path).resolve(), Path(work_dir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    audio_hash = _audio_hash(audio_path)
    manifest_path = work_dir / "audio-manifest.json"
    signature = {"audio_hash": audio_hash, "model": model, "language": language or "", "source": source}
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("signature") != signature:
            raise ProviderError("checkpoint_mismatch", "Saved audio belongs to another source or model. Start a new generation to change transcription settings.")
        completed = work_dir / "transcript.json"
        if completed.exists():
            return Transcript.model_validate_json(completed.read_text(encoding="utf-8"))
    chunks = prepare_chunks(audio_path, work_dir, cancelled)
    _atomic_json(manifest_path, {"signature": signature, "chunks": [asdict(c) for c in chunks]})
    response_dir = work_dir / "responses"
    response_dir.mkdir(exist_ok=True)
    responses = []
    detected_language = language or "unknown"
    for chunk in chunks:
        if cancelled and cancelled(): raise ProviderError("cancelled", "Audio processing was cancelled.")
        response_path = response_dir / f"chunk-{chunk.index:05d}.json"
        if response_path.exists():
            response_body = json.loads(response_path.read_text(encoding="utf-8"))
        else:
            if progress: progress(f"Transcribing audio section {chunk.index+1} of {len(chunks)}")
            form = {"model": model, "response_format": "verbose_json", "timestamp_granularities[]": "segment", "temperature": "0"}
            if language: form["language"] = language
            try:
                with Path(chunk.path).open("rb") as file:
                    response = requests.post("https://api.groq.com/openai/v1/audio/transcriptions", headers={"Authorization": f"Bearer {key}"}, data=form, files={"file": (Path(chunk.path).name, file, "audio/wav")}, timeout=(15, 180))
            except requests.ConnectTimeout as exc:
                raise ProviderError("temporary", "Groq could not establish a connection. Finished audio sections are saved.", 30) from exc
            except requests.Timeout as exc:
                raise ProviderError("uncertain_timeout", "Groq did not finish within the request limit. This section may have used quota. Retry manually; completed sections are saved.") from exc
            except requests.RequestException as exc:
                raise ProviderError("uncertain_request", "The Groq connection was interrupted. This section may have used quota. Retry manually; completed sections are saved.") from exc
            if cancelled and cancelled():
                raise ProviderError("cancelled", "Audio processing was cancelled. An already sent transcription request may still use quota.")
            if not response.ok: raise http_error(response, "Groq")
            try: response_body = response.json()
            except ValueError as exc: raise ProviderError("invalid_output", "Groq did not return a readable transcription.") from exc
            _validate_response(response_body, chunk)
            _atomic_json(response_path, response_body)
        _validate_response(response_body, chunk)
        responses.append(response_body)
        detected_language = response_body.get("language") or detected_language
    snippets, warnings = merge_chunks(chunks, responses)
    video_id = source if re.fullmatch(r"[A-Za-z0-9_-]{11}", source) else None
    transcript = Transcript(source_id=source, video_id=video_id, url=f"https://www.youtube.com/watch?v={source}" if video_id else None, title=f"Audio transcript · {source}", language=detected_language, origin="audio", snippets=snippets, metadata={"provider": "groq", "model": model, "audio_hash": audio_hash, "requested_source_language": language or "", "warnings": warnings, "billing_note": "Free account status is owner-confirmed; Groq account billing cannot be enforced by this request.", "audio_duration": max(c.offset+c.duration for c in chunks), "temporary_audio_retention": "Successful managed audio is deleted by default; failed audio is eligible for cleanup after 24 hours on worker activity. User originals are preserved."})
    _atomic_json(work_dir / "transcript.json", transcript.model_dump(mode="json"))
    if not approval.get("retain_audio", False):
        for chunk in chunks:
            Path(chunk.path).unlink(missing_ok=True)
        # Only delete downloaded copies managed by us, never the user's input.
        if audio_path.parent == work_dir and audio_path.name.startswith("source-audio."):
            audio_path.unlink(missing_ok=True)
    return transcript


def cleanup_temporary_audio(work_dir: Path, older_than_seconds: float = 86400):
    """Bounded retention; only managed audio files inside this job folder."""
    root = Path(work_dir).resolve()
    cutoff = time.time() - older_than_seconds
    for pattern in ["source-audio.*", "chunks/*.wav", "chunks/*.partial.wav"]:
        for path in root.glob(pattern):
            resolved = path.resolve()
            if resolved.is_relative_to(root) and path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()


def transcribe_file(path: Path, work_dir: Path, approval: dict, progress=None, cancelled=None, checkpoint=None, load_checkpoint=None) -> Transcript:
    source = approval.get("source", "")
    if not source.startswith("import:") or not source.removeprefix("import:"):
        raise ProviderError("audio_approval", "Approve the imported audio source before transcription.")
    return transcribe_audio(path, work_dir, approval, source, progress, cancelled, checkpoint, load_checkpoint, language=approval.get("source_language") or None)


def transcribe_youtube(video_id: str, work_dir: Path, approval: dict, progress=None, cancelled=None, checkpoint=None, load_checkpoint=None) -> Transcript:
    video_id = parse_youtube_id(video_id)
    model = approval.get("model", "whisper-large-v3-turbo")
    validate_approval(approval, video_id, model)
    if cancelled and cancelled():
        raise ProviderError("cancelled", "Audio processing was cancelled.")
    # Check key before any media download.
    if not SecretStore().get("groq"):
        raise ProviderError("authentication", "Configure a Groq API key before downloading audio.")
    work_dir = Path(work_dir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    cleanup_temporary_audio(work_dir)
    completed = work_dir / "transcript.json"
    if completed.exists():
        saved = Transcript.model_validate_json(completed.read_text(encoding="utf-8"))
        if saved.source_id == video_id and saved.metadata.get("model") == model and saved.metadata.get("requested_source_language", "") == (approval.get("source_language") or ""):
            return saved
    audio_files = [p for p in work_dir.glob("source-audio.*") if p.suffix.lower() in {".webm", ".m4a", ".mp3", ".ogg", ".opus", ".wav"}]
    if not audio_files:
        if progress: progress("Downloading approved audio")
        command = [sys.executable, "-m", "yt_dlp", "--no-playlist", "--no-progress", "--no-warnings", "--socket-timeout", "30", "--retries", "2", "-f", "bestaudio[language=original]/bestaudio", "--paths", str(work_dir), "-o", "source-audio.%(ext)s", "--", f"https://www.youtube.com/watch?v={video_id}"]
        _run(command, cancelled)
        audio_files = [p for p in work_dir.glob("source-audio.*") if p.suffix.lower() in {".webm", ".m4a", ".mp3", ".ogg", ".opus", ".wav"}]
    if not audio_files: raise ProviderError("audio_failed", "No usable audio was downloaded. Import an audio file or transcript instead.")
    return transcribe_audio(audio_files[0], work_dir, approval, video_id, progress, cancelled, checkpoint, load_checkpoint, language=approval.get("source_language") or None)
