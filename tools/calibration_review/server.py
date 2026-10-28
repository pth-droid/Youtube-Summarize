"""Local review tool for calibration runs: transcript beside extracted ideas, with quick marks.

Usage:  python -m tools.calibration_review.server D:/temp/calibration --port 8771
The run folder comes from `python -m tools.calibration_run`. Marks are saved per video as <run>/<video_id>/review-marks.json. Binds to 127.0.0.1 only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
MARK_VALUES = {"good", "duplicate", "wrong"}
MAX_BODY = 2_000_000


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def videos(run: Path) -> list[dict]:
    result = []
    for folder in sorted(run.iterdir()):
        summary = folder / "calibration-summary.json"
        if not (VIDEO_ID.match(folder.name) and summary.is_file() and (folder / "knowledge.json").is_file()):
            continue
        data, marks = read(summary), folder / "review-marks.json"
        metrics = data["display_metrics"]
        result.append({"id": folder.name, "title": data.get("title") or folder.name, "minutes": metrics["source_minutes"],
                       "chapters": metrics["chapters"], "key_ideas": metrics["chapter_key_ideas"], "leaves": metrics["leaf_units"],
                       "reviewed": marks.is_file()})
    return sorted(result, key=lambda video: video["minutes"] or 0)


def video(run: Path, video_id: str) -> dict:
    folder = run / video_id
    source, knowledge = read(folder / "source.json"), read(folder / "knowledge.json")
    units = {unit["id"]: unit for unit in knowledge["units"]}
    position = {snippet["id"]: index for index, snippet in enumerate(source["snippets"])}

    def leaf(unit):
        return {"id": unit["id"], "title": unit["title"], "summary": unit["summary"], "explanation": unit["explanation"],
                "kind": unit["kind"], "status": unit["status"], "terms": unit["technical_terms"],
                "evidence": [[position[sid] for sid in evidence["snippet_ids"] if sid in position] for evidence in unit["evidence"]]}

    sections = [{"id": s["id"], "title": s["title"], "role": s.get("role", "substantive"), "depth": s.get("depth", "intermediate"),
                 "first": min(position[sid] for sid in s["snippet_ids"]), "last": max(position[sid] for sid in s["snippet_ids"])}
                for s in knowledge["sections"]]
    chapters = [{"id": c["id"], "title": c["title"], "detail": c["detail"], "depth": c["depth"], "substantive_share": c["substantive_share"],
                 "ideas": [{**leaf(units[uid]), "leaves": [leaf(units[cid]) for cid in units[uid]["child_ids"]]} for uid in c["unit_ids"]]}
                for c in knowledge.get("chapters", [])]
    marks_path = folder / "review-marks.json"
    return {"id": video_id, "title": source.get("title", video_id), "video_id": source.get("video_id"),
            "snippets": [{"text": s["text"], "start": s.get("start")} for s in source["snippets"]],
            "sections": sorted(sections, key=lambda s: s["first"]), "chapters": chapters,
            "marks": read(marks_path) if marks_path.is_file() else None}


def clean_marks(body: dict, total: int, unit_ids: set[str]) -> dict:
    """Keep only the expected shape; the browser is trusted but its data is still validated."""
    verdict = body.get("verdict") if isinstance(body.get("verdict"), dict) else {}
    missed = []
    for item in body.get("missed", [])[:500]:
        first, last = int(item.get("first", -1)), int(item.get("last", -1))
        if 0 <= first <= last < total:
            missed.append({"id": str(item.get("id", ""))[:40], "first": first, "last": last, "note": str(item.get("note", ""))[:1000]})
    ideas = {uid: value for uid, value in (body.get("ideas") or {}).items() if uid in unit_ids and value in MARK_VALUES}
    return {"verdict": {"coverage": verdict.get("coverage") if verdict.get("coverage") in {"enough", "missing", "too_much"} else None,
                        "wanted": verdict.get("wanted") if verdict.get("wanted") in {"brief", "detailed"} else None,
                        "note": str(verdict.get("note", ""))[:2000]},
            "missed": missed, "ideas": ideas, "updated_at": datetime.now(timezone.utc).isoformat()}


class Handler(BaseHTTPRequestHandler):
    run: Path
    # Keep-alive with explicit lengths. With HTTP/1.0 the socket closes after each
    # response, and on Windows a close with unread client bytes resets the
    # connection, which can drop the end of a large response.
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):
        pass

    def send(self, status: int, body: bytes, content_type: str):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, value, status=200):
        self.send(status, json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def video_id(self):
        video_id = self.path.rstrip("/").rsplit("/", 1)[-1]
        if not VIDEO_ID.match(video_id) or not (self.run / video_id / "knowledge.json").is_file():
            self.send_json({"error": "unknown video"}, 404)
            return None
        return video_id

    def do_GET(self):
        self.path = self.path.split("?", 1)[0]
        if self.path in ("/", "/index.html"):
            self.send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/videos":
            self.send_json(videos(self.run))
        elif self.path.startswith("/api/video/"):
            video_id = self.video_id()
            if video_id:
                self.send_json(video(self.run, video_id))
        else:
            self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        if not self.path.startswith("/api/marks/"):
            return self.send_json({"error": "not found"}, 404)
        # Same-origin only: a page on another site cannot write marks.
        if self.headers.get("X-Review") != "1":
            return self.send_json({"error": "forbidden"}, 403)
        video_id = self.video_id()
        if not video_id:
            return
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= MAX_BODY:
            return self.send_json({"error": "bad size"}, 413)
        data = video(self.run, video_id)
        unit_ids = {item["id"] for c in data["chapters"] for idea in c["ideas"] for item in [idea, *idea["leaves"]]}
        marks = clean_marks(json.loads(self.rfile.read(length)), len(data["snippets"]), unit_ids)
        target = self.run / video_id / "review-marks.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(marks, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, target)
        self.send_json({"saved": marks["updated_at"]})


def main():
    parser = argparse.ArgumentParser(description="Review calibration runs and mark missed or redundant ideas.")
    parser.add_argument("run", type=Path)
    parser.add_argument("--port", type=int, default=8771)
    args = parser.parse_args()
    Handler.run = args.run.resolve()
    print(f"Calibration review: http://127.0.0.1:{args.port}  (run: {Handler.run})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
