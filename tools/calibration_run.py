"""Run the pipeline on saved transcripts and write what tools.calibration_review needs.

Usage:  python -m tools.calibration_run D:/temp/calibration --provider claude_code
        python -m tools.calibration_run D:/temp/calibration --transcripts .feasibility --videos 0qqW3vxOC-g

Each video lands in <output>/<video_id>/ with page.html, knowledge.json, generation.json and a
calibration-summary.json. Re-running resumes from the checkpoints in each folder, and a video that
already has a summary is skipped. This sends live requests to the chosen subscription provider.
Keep the output path short: Windows paths over 260 characters break the checkpoint files.
"""
from __future__ import annotations

import argparse
import json
import time
import traceback
from pathlib import Path

from distill.models import KnowledgeModel, Transcript
from distill.pipeline import Pipeline
from distill.providers import ClaudeCodeProvider, CodexProvider

PROVIDERS = {"codex": CodexProvider, "claude_code": ClaudeCodeProvider}


def summarise(work_dir: Path) -> dict:
    knowledge = KnowledgeModel.model_validate(json.loads((work_dir / "knowledge.json").read_text(encoding="utf-8")))
    generation = json.loads((work_dir / "generation.json").read_text(encoding="utf-8"))
    sections = {section.id: section for section in knowledge.sections}
    roles: dict[str, int] = {}
    for section in knowledge.sections:
        roles[section.role] = roles.get(section.role, 0) + len(section.snippet_ids)
    return {
        "title": None, "duration_seconds": generation["duration_seconds"],
        "display_metrics": generation["display_metrics"], "section_roles_by_snippets": roles,
        "chapters": [{"title": chapter.title, "depth": chapter.depth, "substantive_share": chapter.substantive_share,
                      "detail": chapter.detail, "key_ideas": len(chapter.unit_ids),
                      "section_depths": [sections[section_id].depth for section_id in chapter.section_ids]}
                     for chapter in knowledge.chapters],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the pipeline on saved transcripts for calibration review.")
    parser.add_argument("output", type=Path)
    parser.add_argument("--transcripts", type=Path, default=Path(".feasibility"), help="folder of <video_id>.json transcripts")
    parser.add_argument("--videos", nargs="*", help="video ids to run (default: every transcript in the folder)")
    parser.add_argument("--provider", choices=sorted(PROVIDERS), default="claude_code")
    parser.add_argument("--language", default="vi")
    parser.add_argument("--timeout", type=int, default=900, help="seconds allowed for one provider call")
    args = parser.parse_args()

    video_ids = args.videos or sorted(path.stem for path in args.transcripts.glob("*.json"))
    args.output.mkdir(parents=True, exist_ok=True)
    log = (args.output / "runner.log").open("a", encoding="utf-8")

    def say(*parts) -> None:
        line = time.strftime("%H:%M:%S ") + " ".join(str(part) for part in parts)
        print(line, flush=True)
        log.write(line + "\n")
        log.flush()

    failed = 0
    for video_id in video_ids:
        work_dir = args.output / video_id
        summary_path = work_dir / "calibration-summary.json"
        if summary_path.exists():
            say(video_id, "already done")
            continue
        source = Transcript.model_validate(json.loads((args.transcripts / f"{video_id}.json").read_text(encoding="utf-8")))
        say(video_id, "start", f"{len(source.snippets)} snippets", source.title[:70])
        started = time.monotonic()
        try:
            Pipeline(PROVIDERS[args.provider](timeout_seconds=args.timeout)).run(
                source, {"language": args.language}, work_dir,
                progress=lambda stage, details, video_id=video_id: say(video_id, stage, details.get("message", "")))
            summary = summarise(work_dir)
            summary["title"] = source.title
            summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            metrics = summary["display_metrics"]
            say(video_id, "done", f"{(time.monotonic() - started) / 60:.1f} min", "chapters", metrics["chapters"],
                metrics["chapter_detail_levels"], "key ideas", metrics["chapter_key_ideas"],
                "note leaves", metrics["note_leaf_units"], "/", metrics["leaf_units"])
        except Exception as error:  # Keep going; the work directory keeps checkpoints for a retry.
            failed += 1
            say(video_id, "FAILED", type(error).__name__, str(error)[:300])
            log.write(traceback.format_exc() + "\n")
    say("all videos processed" + (f", {failed} failed" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
