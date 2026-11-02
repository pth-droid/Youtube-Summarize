"""Transcribe one prepared WAV with faster-whisper on the CPU.

Run by distill.audio in whichever Python has faster-whisper installed (the app's own,
or Reelcrew's Whisper runtime), so it imports nothing from distill. It prints one JSON
line per finished segment for progress and writes the whole result to the output file.
"""
import json
import os
import sys
from pathlib import Path


def samples(path: str):
    """The 16 kHz mono 16-bit WAV the app prepared, as floats. Passing samples skips PyAV, whose
    newer releases reject an argument some faster-whisper versions still pass when decoding a file."""
    import wave
    import numpy
    with wave.open(path, "rb") as recording:
        return numpy.frombuffer(recording.readframes(recording.getnframes()), dtype=numpy.int16).astype(numpy.float32) / 32768


def main(audio: str, model: str, language: str, output: str) -> None:
    from faster_whisper import WhisperModel

    whisper = WhisperModel(model, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4)
    # VAD skips silence, where Whisper tends to invent text; without carried-over context
    # one bad segment cannot start a repeating loop.
    pieces, info = whisper.transcribe(samples(audio), language=language or None, vad_filter=True, condition_on_previous_text=False)
    print(json.dumps({"duration": info.duration}), flush=True)
    segments = []
    for piece in pieces:
        text = piece.text.strip()
        if text:
            segments.append({"start": piece.start, "end": piece.end, "text": text, "avg_logprob": piece.avg_logprob, "no_speech_prob": piece.no_speech_prob})
        print(json.dumps({"done": piece.end}), flush=True)
    partial = Path(output + ".partial")
    partial.write_text(json.dumps({"language": info.language, "duration": info.duration, "segments": segments}, ensure_ascii=False), encoding="utf-8")
    partial.replace(output)


if __name__ == "__main__":
    main(*sys.argv[1:5])
