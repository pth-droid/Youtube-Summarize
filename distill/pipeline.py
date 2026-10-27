"""Bounded semantic analysis; the model reasons, Python preserves and validates."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from time import monotonic
from types import SimpleNamespace
from typing import Any, Callable

from .models import (
    SCHEMA_VERSION, SKILL_VERSION, Chapter, Extraction, FigurePlan, FigureSet, GroundingCorrections, GroundingReview,
    KnowledgeModel, KnowledgeUnit, LectureFrame, LectureParts, LecturePlan, PresentationPlan, Relationship, Snippet,
    Synthesis, Transcript, normalize_quote, validate_bundle, validate_figures, validate_grounding, validate_lecture,
)
from .apparatus import catalogue
from .chapters import assign_units, chapter_profile, detail_level, split_sections
from .renderer import render_lecture, render_page
from .providers import ProviderError
from .model_profiles import resolve_profile
from .metrics import display_metrics, evenly_spaced, source_positions, spread_by_source_position

SKILL_DIR = Path(__file__).resolve().parents[1] / "skills" / "visual-synthesis"
# Kept outside SKILL_DIR: its files feed the analysis fingerprint, and lecture
# guidance must not invalidate saved analysis.
LECTURE_SKILL_DIR = SKILL_DIR.parent / "lecture-slides"
FIGURE_SKILL_DIR = SKILL_DIR.parent / "process-figures"
PIPELINE_REVISION = "2.0"
# Versioned separately so a presentation change does not invalidate saved extraction and synthesis.
PRESENTATION_REVISION = "2"
LECTURE_REVISION = "1"
FIGURE_REVISION = "1"
# Figures are considered only for sources that explain mechanisms or procedures.
PROCESS_KINDS = ("mechanism", "step")
SLIDE_RANGE = {"brief": "1-2", "standard": "2-4", "detailed": "3-6"}
DETAIL_KINDS = ("step", "choice", "objection", "mechanism")


class PipelineError(RuntimeError):
    def __init__(self, message: str, diagnostics: dict | None = None):
        super().__init__(message)
        self.diagnostics = diagnostics or {}


class PipelineCancelled(PipelineError):
    pass


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def prepare_source(source: Transcript, max_snippet_chars: int = 1800) -> Transcript:
    """Split exceptionally large imports, retaining exact text and original timing."""
    result = []
    changed = False
    for snippet in source.snippets:
        if len(snippet.text) <= max_snippet_chars:
            result.append(snippet)
            continue
        changed = True
        pieces = []
        text = snippet.text
        while len(text) > max_snippet_chars:
            split = text.rfind(" ", 0, max_snippet_chars)
            if split < max_snippet_chars // 2:
                split = max_snippet_chars
            pieces.append(text[:split])
            text = text[split:]
        if text:
            pieces.append(text)
        for index, piece in enumerate(pieces):
            result.append(Snippet(**{**snippet.model_dump(), "id": f"{snippet.id}.p{index + 1:03d}", "text": piece}))
    if not changed:
        return source
    data = source.model_dump()
    data.update(snippets=result, content_hash="")
    data["metadata"] = {**source.metadata, "original_content_hash": source.content_hash, "large_snippets_split": True,
                        "split_timing_note": "Split fragments share their original span; their exact individual time is unknown."}
    return Transcript.model_validate(data)


def semantic_snippet(snippet: Snippet) -> dict:
    """Send original words and stable references, not repeated display metadata.

    Order is chronological/source order. Exact original timing stays in the source
    artifact and the renderer resolves each cited ID back to that full record.
    """
    record = {"id": snippet.id, "text": snippet.text}
    if snippet.speaker:
        record["speaker"] = snippet.speaker
    return record


def constrain_source_ids(schema: dict, body: dict) -> set[str]:
    """Prevent stray words in IDs without restricting custom imported source IDs.

    The downstream validator still checks exact membership and original order.
    The short schema pattern avoids repeating hundreds of IDs in the schema.
    """
    passages = body.get("snippets", body.get("original_passages", []))
    ids = {passage["id"] for passage in passages if isinstance(passage, dict) and "id" in passage}
    if not ids or not all(re.fullmatch(r"[A-Za-z0-9_.:-]+", sid) for sid in ids):
        return ids
    family = r"s[0-9]{6}(?:\.p[0-9]{3})?"
    pattern = family if all(re.fullmatch(family, sid) for sid in ids) else r"[A-Za-z0-9_.:-]+"
    definitions = schema.get("$defs", {})
    for name in ("Evidence", "SourceSection"):
        properties = definitions.get(name, {}).get("properties", {})
        if "snippet_ids" in properties:
            properties["snippet_ids"]["items"]["pattern"] = f"^{pattern}$"
        if "range_end" in properties:
            properties["range_end"]["pattern"] = f"^(?:{pattern})?$"
    return ids


def invalid_source_ids(data: Any, known: set[str]) -> list[str]:
    """Return bounded concrete reference errors for the model's repair prompt."""
    errors = []
    def visit(value):
        if isinstance(value, dict):
            cited = value.get("snippet_ids", [])
            if isinstance(cited, list):
                for sid in cited:
                    if isinstance(sid, str) and sid not in known and sid not in errors:
                        errors.append(sid)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    if known:
        visit(data)
    return errors[:6]


def quote_mismatch_feedback(result: Any, body: dict) -> list[dict]:
    """Point the model at exact source words for a bounded evidence repair."""
    passages = body.get("snippets", body.get("original_passages", []))
    originals = {item["id"]: item["text"] for item in passages
                 if isinstance(item, dict) and isinstance(item.get("id"), str)
                 and isinstance(item.get("text"), str)}
    problems = []
    for item in [*getattr(result, "units", []), *getattr(result, "relationships", [])]:
        for evidence in getattr(item, "evidence", []):
            if not all(sid in originals for sid in evidence.snippet_ids):
                continue
            original = " ".join(originals[sid] for sid in evidence.snippet_ids)
            if normalize_quote(evidence.quote) not in normalize_quote(original):
                problems.append({"item_id": item.id, "source_ids": evidence.snippet_ids,
                                 "rejected_quote": evidence.quote[:400], "exact_source_words": original[:2500]})
            if len(problems) == 3:
                return problems
    return problems


def source_windows(source: Transcript, budget: int, overlap: int = 1, compact: bool = False) -> list[list[Snippet]]:
    """Cover every snippet. Overlap retains boundary context without advancing gaps."""
    if budget < 2500:
        raise PipelineError("The selected model context is too small for a grounded source window.")
    windows, start = [], 0
    while start < len(source.snippets):
        end, used = start, 0
        while end < len(source.snippets):
            record = semantic_snippet(source.snippets[end]) if compact else source.snippets[end].model_dump()
            size = len(json.dumps(record, ensure_ascii=False)) + 2
            if used + size > budget:
                break
            used += size
            end += 1
        if end == start:
            raise PipelineError("A source snippet exceeds the available model context.")
        windows.append(source.snippets[start:end])
        if end == len(source.snippets):
            break
        start = max(start + 1, end - max(0, overlap))
    return windows


def analysis_fingerprint(source, preferences, provider, windows):
    skill_digest = hashlib.sha256("\n".join(path.read_text(encoding="utf-8")
        for path in sorted(SKILL_DIR.rglob("*.md"))).encode("utf-8")).hexdigest()
    return hashlib.sha256(json.dumps({"source": source.content_hash, "preferences": preferences,
        "provider": getattr(provider, "name", "unknown"), "model": getattr(provider, "model", "default"),
        "skill": SKILL_VERSION, "schema": SCHEMA_VERSION, "pipeline": PIPELINE_REVISION,
        "reasoning_effort": getattr(provider, "reasoning_effort", "provider default"),
        "model_profile": resolve_profile(provider).as_dict(),
        "skill_digest": skill_digest, "window_plan": [[s.id for s in window] for window in windows]}, sort_keys=True).encode()).hexdigest()


def namespace_extraction(extraction: Extraction, prefix: str) -> Extraction:
    mapping = {u.id: f"{prefix}_{u.id}" for u in extraction.units}
    if len(mapping) != len(extraction.units):
        raise ValueError("Duplicate extracted unit IDs")
    for unit in extraction.units:
        if unit.child_ids:
            raise ValueError("Extraction units must not invent unsupplied child records")
        unit.id = mapping[unit.id]
    for rel in extraction.relationships:
        if rel.source not in mapping or rel.target not in mapping:
            raise ValueError("Extraction relationship references an unknown unit")
        rel.id = f"{prefix}_{rel.id}"
        rel.source, rel.target = mapping[rel.source], mapping[rel.target]
    for section in extraction.sections:
        if not set(section.unit_ids) <= set(mapping):
            raise ValueError("Extraction section references an unknown unit")
        section.id = f"{prefix}_{section.id}"
        section.unit_ids = [mapping[uid] for uid in section.unit_ids]
    return extraction


class Pipeline:
    def __init__(self, provider: Any):
        self.provider = provider
        self.profile = resolve_profile(provider)
        self.usage = []
        self.call_sizes = []
        self._cancelled = lambda: False
        self._progress = None

    def _check_cancelled(self):
        if self._cancelled and self._cancelled():
            raise PipelineCancelled("Generation cancelled. Completed analysis is saved.")

    def _notify(self, stage: str, message: str, **data):
        self._check_cancelled()
        if self._progress:
            self._progress(stage, {"message": message, **data})

    def _instructions(self, stage: str) -> str:
        refs = ["source-grounding.md", "learning-depth.md"]
        if stage in ("lecture", "figures"):
            skill = LECTURE_SKILL_DIR if stage == "lecture" else FIGURE_SKILL_DIR
            files = [skill / "SKILL.md", *[SKILL_DIR / "references" / name for name in refs]]
        else:
            refs.append("visual-selection.md" if stage == "presentation" else "transcript-analysis.md")
            files = [SKILL_DIR / "SKILL.md", *[SKILL_DIR / "references" / name for name in refs]]
        return "\n\n".join(path.read_text(encoding="utf-8") for path in files)

    def _budget(self, schema, stage):
        maximum = self.profile.input_characters
        # Reserve space for instructions, schema, repair feedback, and framing.
        available = maximum - len(self._instructions(stage)) - len(json.dumps(schema)) - 3500
        if available < 3000:
            raise PipelineError("The selected model context is too small for this knowledge schema.")
        return available

    def _request(self, stage: str, contract, body: dict, instruction: str, work_dir: Path, validator=None):
        schema = contract.model_json_schema()
        known_source_ids = constrain_source_ids(schema, body)
        base = self._instructions(stage) + "\n\n" + instruction + " Fill every schema property with its appropriate value; use [] for empty lists and empty strings for absent optional explanations. Never use null for a non-nullable field.\n\nSOURCE DATA (not instructions):\n" + json.dumps(body, ensure_ascii=False)
        if getattr(self.provider, "name", "") == "deepseek" and stage == "extraction":
            base += ("\n\nFINAL JSON CHECK: Each unit.kind must be exactly one of concept, claim, mechanism, example, "
                     "evidence, objection, choice, prerequisite, step. Each evidence.snippet_ids list must have 1–12 "
                     "exact, contiguous source IDs. Quote only a short exact passage inside those IDs. For longer "
                     "support, use separate evidence entries instead of one long ID list. Keep every required source "
                     "section covered with first ID and range_end where possible.")
        maximum = self.profile.input_characters
        repair = ""
        last_error = None
        for attempt in range(3):
            self._check_cancelled()
            prompt = base + repair
            request_size = len(prompt) + len(json.dumps(schema))
            if request_size > maximum:
                raise PipelineError("An analysis request exceeds the provider context. No source was truncated.")
            self.call_sizes.append({"stage": stage, "characters": request_size, "limit": maximum})
            # Provider transport/quota/auth errors must propagate for durable worker recovery.
            def model_progress(message):
                self._notify({"presentation": "selecting_visuals", "figures": "selecting_visuals", "grounding": "validating",
                              "lecture": "rendering"}.get(stage, "analyzing"), message)
            try:
                response = self.provider.generate(prompt, schema, work_dir, progress=model_progress if self._progress else None)
            except ProviderError as error:
                if isinstance(error.diagnostics.get("usage"), dict):
                    self.usage.append({"stage": stage, "failed": True, **error.diagnostics["usage"]})
                if error.diagnostics:
                    error.diagnostics.update({"stage": stage, "stage_attempt": attempt + 1,
                                              "request_size_characters": request_size})
                    if isinstance(body.get("window_index"), int):
                        error.diagnostics["source_window"] = body["window_index"] + 1
                if error.code == "invalid_output" and error.diagnostics.get("failure") == "invalid_json" and attempt < 2:
                    repair = "\n\nThe previous answer was not a readable JSON object. Return one complete JSON object matching the schema."
                    continue
                raise
            data = response.data if hasattr(response, "data") else response
            if hasattr(response, "usage"):
                self.usage.append({"stage": stage, **(response.usage or {})})
            try:
                result = None
                result = contract.model_validate(data)
                if validator:
                    validator(result)
                return result
            except (ValueError, TypeError) as exc:
                last_error = exc
                # No raw response/logs in user-facing errors; feedback stays in this bounded request.
                repair = "\n\nThe previous output did not validate. Return a complete corrected artifact. Validation details: " + str(exc)[:1600]
                malformed_ids = invalid_source_ids(data, known_source_ids)
                if malformed_ids:
                    repair += " Invalid source IDs: " + json.dumps([sid[:100] for sid in malformed_ids], ensure_ascii=False) + ". Copy IDs exactly from supplied original passages, without added words. Do not invent or silently substitute evidence."
                if result is not None and "quote is not present in its original source span" in str(exc):
                    mismatches = quote_mismatch_feedback(result, body)
                    if mismatches:
                        repair += " Exact quote repairs: " + json.dumps(mismatches, ensure_ascii=False) + ". Copy a short exact substring from the cited words without translation or changed punctuation. If it cannot support the claim, narrow or mark the claim uncertain."
        validation = {"type": type(last_error).__name__}
        if callable(getattr(last_error, "errors", None)):
            validation["fields"] = [{"location": [str(part) for part in item.get("loc", ())],
                                      "rule": item.get("type", "invalid")}
                                     for item in last_error.errors()[:6]]
        else:
            # Only these owned validator messages are known to contain no
            # source text, provider response, or credential values.
            safe_reasons = (
                "Every source snippet in this window must belong to a section",
                "Evidence must cite this window's source IDs",
                "A section range needs one first ID and one last ID",
                "Source section range is reversed",
                "Corrected evidence must stay inside this source window",
                "references missing source snippets",
                "evidence must cite a contiguous source span in original order",
                "quote is not present in its original source span",
                "Extraction units must not invent unsupplied child records",
                "Extraction relationship references an unknown unit",
                "Extraction section references an unknown unit",
                "Source claims and inferences require original evidence",
                "A source relationship or inference needs evidence",
            )
            validation["rule"] = next((reason for reason in safe_reasons if reason in str(last_error)), "other_validation_error")
        details = {"stage": stage, "stage_attempts": 3, "validation": validation}
        if isinstance(body.get("window_index"), int):
            details["source_window"] = body["window_index"] + 1
        raise PipelineError(f"The model returned invalid {stage} data after three attempts. Saved progress can be retried.", diagnostics=details) from last_error

    def _original_context(self, source, items, neighbors=2, allowed=None):
        snippets = {s.id: s for s in source.snippets}
        wanted = {sid for item in items for ev in item.evidence for sid in ev.snippet_ids}
        positions = {snippet.id: index for index, snippet in enumerate(source.snippets)}
        for sid in list(wanted):
            if sid in positions:
                index = positions[sid]
                wanted.update(s.id for s in source.snippets[max(0, index - neighbors):index + neighbors + 1])
        if allowed is not None:
            wanted &= allowed
        return [semantic_snippet(s) for s in source.snippets if s.id in wanted and s.id in snippets]

    def _review(self, source, units, relationships, work_dir, allowed=None, repair=True):
        items = [*units, *relationships]
        if not items:
            return []
        budget = self._budget(GroundingReview.model_json_schema(), "grounding")
        def review_body(group):
            # Quotes already passed exact-source validation. Resolve their IDs
            # to deduplicated original passages rather than repeating the same
            # long quotation in every concept and relationship record.
            records = []
            for item in group:
                record = item.model_dump()
                record["evidence"] = [{"snippet_ids": evidence.snippet_ids} for evidence in item.evidence]
                records.append(record)
            return {"items": records, "original_passages": self._original_context(source, group, 6, allowed)}
        groups, current = [], []
        for item in items:
            trial = [*current, item]
            body = review_body(trial)
            if len(json.dumps(body, ensure_ascii=False)) > budget:
                if not current:
                    raise PipelineError("A knowledge record has too much evidence for the selected context.")
                groups.append(current)
                current = [item]
            else:
                current = trial
        if current:
            groups.append(current)
        warnings = []
        for index, group in enumerate(groups):
            self._notify("validating", f"Reviewing source grounding {index + 1} of {len(groups)}", completed=index, total=len(groups))
            body = review_body(group)
            def validate_review(review):
                if any(issue.item_id not in {i.id for i in group} for issue in review.issues):
                    raise ValueError("Review references an unknown item")
            review = self._request("grounding", GroundingReview, body,
                "Independently compare every item and relationship against original passages. Evidence IDs resolve to original_passages; quotations are not repeated in item records. Check causality, numbers, attribution, negation, qualifiers, and visual dependence. Each significant fact in title, summary and explanation should be supported by its cited IDs, not merely by uncited neighboring context. When neighboring context supports an omitted fact, report the missing supporting citation precisely, rather than declaring the entire source lacks that fact. Do not fact-check using outside knowledge. Report only concrete unsupported/overstated/contradicted/missing-caveat items. Inference must remain explicitly labelled; background must not borrow source evidence. Child records are stored separately; do not report their absence as a grounding issue. Limitations should be specific to these claims; omit repeated generic warnings about no external fact-checking. Reasons and limitations use the same language as the supplied explanations.",
                work_dir, validate_review)
            item_map = {item.id: item for item in group}
            if repair and review.issues:
                problem_ids = {issue.item_id for issue in review.issues}
                selected = [item for item in group if item.id in problem_ids]
                repair_body = {"issues": [issue.model_dump() for issue in review.issues],
                    "units": [item.model_dump() for item in selected if isinstance(item, KnowledgeUnit)],
                    "relationships": [item.model_dump() for item in selected if isinstance(item, Relationship)],
                    "known_units": [{"id": u.id, "title": u.title} for u in units],
                    "original_passages": self._original_context(source, selected, 6, allowed)}
                def validate_corrections(value):
                    if {item.id for item in [*value.units, *value.relationships]} != problem_ids:
                        raise ValueError("Corrections must preserve exactly the reviewed item IDs")
                    for item in value.units:
                        if item.id not in {u.id for u in units} or item.child_ids != item_map[item.id].child_ids:
                            raise ValueError("Corrections must preserve knowledge IDs and child references")
                    for relation in value.relationships:
                        if relation.id not in {r.id for r in relationships}:
                            raise ValueError("Correction changed a relationship ID")
                        if relation.source not in {u.id for u in units} or relation.target not in {u.id for u in units}:
                            raise ValueError("Corrected relationship references an unknown unit")
                    if allowed is not None and any(sid not in allowed for item in [*value.units, *value.relationships] for ev in item.evidence for sid in ev.snippet_ids):
                        raise ValueError("Corrected evidence must stay inside this source window")
                    validate_grounding(source, value.units, value.relationships)
                try:
                    correction = self._request("grounding", GroundingCorrections, repair_body,
                        "Correct only the listed grounding defects. Preserve item IDs, original child_ids, output language, and relevant qualifications. Use only supplied original passages for evidence. Add missing original citations or narrow unsupported text. Correct a reversed relationship direction only when source evidence supports the corrected direction; otherwise mark it uncertain with a caveat. Return exactly the listed units and relationships, no additional records.",
                        work_dir, validate_corrections)
                except PipelineError:
                    correction = None
                if correction is not None:
                    corrected = {item.id: item for item in [*correction.units, *correction.relationships]}
                    for item in selected:
                        replacement = corrected[item.id]
                        for key in type(replacement).model_fields:
                            setattr(item, key, getattr(replacement, key))
                    # One corrective pass, followed by a separate review. Any
                    # remaining defect stays visible; never loop until agreement.
                    warnings.extend(self._review(source,
                        [item for item in group if isinstance(item, KnowledgeUnit)],
                        [item for item in group if isinstance(item, Relationship)], work_dir, allowed, repair=False))
                    warnings.extend(review.limitations)
                    continue
            for issue in review.issues:
                item = item_map[issue.item_id]
                item.status = "uncertain"
                note = f"Source review: {issue.reason}"
                item.caveats.append(note)
                warnings.append(f"{item.id}: {issue.reason}")
            warnings.extend(review.limitations)
        return warnings

    def _synthesis_body(self, source, units, relationships, preferences):
        valid = {u.id for u in units}
        # Original quotes and source passages remain alongside these records.
        return {"preferences": preferences, "source_title": source.title,
                "units": [{**u.model_dump(), "explanation": u.explanation[:1000]} for u in units],
                "relationships": [r.model_dump() for r in relationships if r.source in valid and r.target in valid],
                "original_passages": self._original_context(source, units)}

    def _group_units(self, source, units, relationships, preferences, budget):
        groups, current = [], []
        for unit in units:
            trial = [*current, unit]
            if len(json.dumps(self._synthesis_body(source, trial, relationships, preferences), ensure_ascii=False)) > budget:
                if not current:
                    raise PipelineError("A synthesized idea exceeds available context. Details remain saved.")
                groups.append(current)
                current = [unit]
            else:
                current = trial
        if current:
            groups.append(current)
        return groups

    def _lecture(self, source, knowledge, preferences, work_dir, load, save) -> LecturePlan:
        """Teach the validated knowledge as slides, chapter by chapter. No new source analysis happens here."""
        units = {u.id: u for u in knowledge.units}
        order = {u.id: index for index, u in enumerate(knowledge.units)}
        positions = source_positions(source)
        section_units = {s.id: s.unit_ids for s in knowledge.sections}
        overview = SimpleNamespace(id="overview", title=knowledge.main_question, section_ids=[], unit_ids=knowledge.overview_ids, detail="standard")
        budget = self._budget(LectureParts.model_json_schema(), "lecture")

        def unit_record(unit, explanation):
            return {"id": unit.id, "title": unit.title, "summary": unit.summary, "explanation": unit.explanation[:explanation],
                    "kind": unit.kind, "status": unit.status, "caveats": unit.caveats[:3], "technical_terms": unit.technical_terms[:6],
                    "has_original_quote": bool(unit.evidence)}

        def chapter_body(chapter):
            ids = list(dict.fromkeys([*chapter.unit_ids, *(uid for sid in chapter.section_ids for uid in section_units.get(sid, []))]))
            if not ids:
                return None  # greetings, small talk or a sponsor read
            key = [units[uid] for uid in chapter.unit_ids]
            rest = [units[uid] for uid in ids if uid not in set(chapter.unit_ids)]
            # Smaller context windows get fewer supporting ideas and shorter explanations; key ideas always stay.
            for limit, explanation in ((14, 600), (9, 250), (5, 0)):
                chosen = sorted(key + spread_by_source_position(rest, positions, max(0, limit - len(key))), key=lambda u: order[u.id])
                chosen_ids = {u.id for u in chosen}
                body = {"id": chapter.id, "title": chapter.title, "slides": SLIDE_RANGE.get(chapter.detail, "2-4"),
                        "units": [unit_record(u, explanation) for u in chosen],
                        "relationships": [{"source": r.source, "target": r.target, "label": r.label, "kind": r.kind, "status": r.status}
                                          for r in knowledge.relationships if r.source in chosen_ids and r.target in chosen_ids][:12]}
                if len(json.dumps(body, ensure_ascii=False)) <= budget:
                    break
            return body

        bodies = [body for body in map(chapter_body, knowledge.chapters) if body] or [chapter_body(overview)]
        per_call = max(1, min(6, self.profile.output_tokens * 3 // 5 // 2400))
        batches, current, size = [], [], 0
        for body in bodies:
            length = len(json.dumps(body, ensure_ascii=False))
            if current and (len(current) >= per_call or size + length > budget):
                batches.append(current)
                current, size = [], 0
            current.append(body)
            size += length
        batches.append(current)

        def check_parts(value, batch):
            if [part.chapter_id for part in value.parts] != [body["id"] for body in batch]:
                raise ValueError("Return one part for each supplied chapter, in the supplied order")
            allowed = {body["id"]: {u["id"] for u in body["units"]} for body in batch}
            for part in value.parts:
                for slide in part.slides:
                    if not set(slide.unit_ids) <= allowed[part.chapter_id]:
                        raise ValueError("A slide cites ideas that were not supplied for its chapter")
                    if slide.layout == "quote" and not any(units[uid].evidence for uid in slide.unit_ids):
                        raise ValueError("A quote slide needs an idea with original evidence")

        context = {"language": preferences["language"], "knowledge_level": preferences["knowledge_level"],
                   "learning_goal": preferences["learning_goal"], "lecture_topic": knowledge.main_question}
        parts = []
        for index, batch in enumerate(batches):
            name = f"lecture_r{LECTURE_REVISION}_{index + 1:02d}"
            result, cached = None, load(name)
            if cached is not None:
                try:
                    result = LectureParts.model_validate(cached)
                    check_parts(result, batch)
                except ValueError:
                    result = None  # an older batch plan; write this part again
            if result is None:
                self._notify("rendering", f"Writing lecture slides, part {index + 1} of {len(batches)}")
                result = self._request("lecture", LectureParts, context | {"chapters": batch},
                    "Write lecture slides for each supplied chapter, one part per chapter in the supplied order. Use the chapter's slide range. Cite only that chapter's supplied idea IDs.",
                    work_dir, lambda value, batch=batch: check_parts(value, batch))
                save(name, result.model_dump(mode="json"))
            parts.extend(result.parts)

        name = f"lecture_r{LECTURE_REVISION}_frame"
        frame_ids = list(dict.fromkeys([*knowledge.overview_ids, *(uid for chapter in knowledge.chapters for uid in chapter.unit_ids)]))[:24]
        def check_frame(value):
            if any(not set(question.unit_ids) <= set(frame_ids) for question in value.questions):
                raise ValueError("A quiz question cites ideas that were not supplied")
        frame, cached = None, load(name)
        if cached is not None:
            try:
                frame = LectureFrame.model_validate(cached)
                check_frame(frame)
            except ValueError:
                frame = None
        if frame is None:
            self._notify("rendering", "Writing lecture objectives and quiz")
            titles = {body["id"]: body["title"] for batch in batches for body in batch}
            body = context | {"source_title": source.title, "main_question": knowledge.main_question,
                "main_conclusion": knowledge.main_conclusion, "main_conclusion_caveats": knowledge.main_conclusion_caveats,
                "chapters": [titles[part.chapter_id] for part in parts],
                "units": [{"id": units[uid].id, "title": units[uid].title, "summary": units[uid].summary, "kind": units[uid].kind,
                           "status": units[uid].status} for uid in frame_ids]}
            frame = self._request("lecture", LectureFrame, body,
                "Write the lecture title, learning objectives, takeaways and three to five quiz questions. Questions cite only supplied idea IDs.",
                work_dir, check_frame)
            save(name, frame.model_dump(mode="json"))
        lecture = LecturePlan(**frame.model_dump(), parts=parts)
        validate_lecture(knowledge, lecture)
        write_json(work_dir / "lecture.json", lecture.model_dump(mode="json"))
        return lecture

    def _figures(self, source, knowledge, preferences, work_dir, load, save) -> FigurePlan:
        """Fill fixed figure forms for physical and procedural ideas. No new source analysis happens here."""
        if sum(u.kind in PROCESS_KINDS for u in knowledge.units) < 2:
            plan = FigurePlan()
            write_json(work_dir / "figures.json", plan.model_dump(mode="json"))
            return plan
        name = f"figures_r{FIGURE_REVISION}"
        plan, cached = None, load(name)
        if cached is not None:
            try:
                plan = FigurePlan.model_validate(cached)
                validate_figures(knowledge, plan)
            except ValueError:
                plan = None  # an older figure plan; choose the figures again
        if plan is None:
            units = {u.id: u for u in knowledge.units}
            order = {u.id: index for index, u in enumerate(knowledge.units)}
            positions = source_positions(source)
            key_ids = list(dict.fromkeys([*knowledge.overview_ids, *(uid for chapter in knowledge.chapters for uid in chapter.unit_ids)]))
            # Mechanisms, steps, examples and ideas with numbers carry what figures show; spread them over the whole source.
            candidates = [u for u in knowledge.units if u.id not in key_ids
                          and (u.kind in (*PROCESS_KINDS, "example") or re.search(r"\d", u.summary + u.explanation))]
            budget = self._budget(FigureSet.model_json_schema(), "figures")

            def record(unit, explanation, quote):
                return {"id": unit.id, "title": unit.title, "summary": unit.summary, "explanation": unit.explanation[:explanation],
                        "kind": unit.kind, "status": unit.status, "caveats": unit.caveats[:2],
                        "original_quote": unit.evidence[0].quote[:quote] if unit.evidence and quote else ""}

            for limit, explanation, quote in ((44, 700, 260), (30, 360, 160), (18, 160, 0)):
                chosen = [units[uid] for uid in key_ids[:limit]]
                chosen += spread_by_source_position(candidates, positions, max(0, limit - len(chosen)))
                chosen.sort(key=lambda u: order[u.id])
                ids = {u.id for u in chosen}
                relationships = sorted((r for r in knowledge.relationships if r.source in ids and r.target in ids),
                                       key=lambda r: r.kind != "causes")[:40]
                body = {"language": preferences["language"], "knowledge_level": preferences["knowledge_level"],
                        "learning_goal": preferences["learning_goal"], "main_question": knowledge.main_question,
                        "templates": catalogue(), "units": [record(u, explanation, quote) for u in chosen],
                        "relationships": [{"id": r.id, "source": r.source, "target": r.target, "kind": r.kind, "label": r.label,
                                           "status": r.status} for r in relationships]}
                if len(json.dumps(body, ensure_ascii=False)) <= budget:
                    break
            allowed_relationships = {r.id for r in relationships}
            self._notify("selecting_visuals", "Choosing figures for processes, apparatus and quantities")
            result = self._request("figures", FigureSet, body,
                "Choose zero to four figures for the supplied ideas, following the figure guidance. Cite only supplied idea IDs and, for what-if effects, only supplied causes relationships. Use only slot and path IDs of the supplied templates. Return an empty list when no figure would explain better than text.",
                work_dir, lambda value: validate_figures(knowledge, value, ids, allowed_relationships))
            plan = FigurePlan(figures=result.figures)
            save(name, plan.model_dump(mode="json"))
        write_json(work_dir / "figures.json", plan.model_dump(mode="json"))
        return plan

    def run(self, source, preferences, work_dir, progress=None, cancelled=None, checkpoint=None, load_checkpoint=None):
        self._progress, self._cancelled = progress, cancelled or (lambda: False)
        self.usage, self.call_sizes = [], []
        cached_stages = set()
        started = monotonic()
        work_dir = Path(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        original = source if isinstance(source, Transcript) else Transcript.model_validate(source)
        source = prepare_source(original)
        language = preferences.get("language", preferences.get("output_language", "vi"))
        if language not in ("vi", "en"):
            language = "vi"
        # The output format only changes the final stages, so it stays out of the analysis fingerprint.
        output_format = "lecture" if preferences.get("output_format") == "lecture" else "page"
        preferences = {"language": language, "knowledge_level": preferences.get("knowledge_level", "balanced"),
                       "learning_goal": preferences.get("learning_goal", preferences.get("goal", ""))}
        write_json(work_dir / "source.json", source.model_dump(mode="json"))
        # Cache identity includes the exact preprocessing/window plan. Changing
        # packing cannot reuse an artifact from a narrower, incompatible window.
        # Plan against input AND estimated output space. This is an app policy,
        # not a tokenizer or a claim about the provider's advertised capacity.
        output_bound = int(self.profile.output_tokens * 2.5)
        window_budget = min(self.profile.extraction_characters, output_bound,
                            self._budget(Extraction.model_json_schema(), "extraction"))
        windows = source_windows(source, window_budget, compact=True)
        adaptive_events = []
        completed_windows = 0
        fingerprint = analysis_fingerprint(source, preferences, self.provider, windows)

        def load(name):
            value = load_checkpoint(name) if load_checkpoint else None
            if value is None:
                path = work_dir / "checkpoints" / f"{name}.json"
                if path.exists():
                    value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict) and value.get("fingerprint") == fingerprint:
                cached_stages.add(name)
                return value.get("data")
            return None

        def save(name, data):
            record = {"fingerprint": fingerprint, "data": data}
            write_json(work_dir / "checkpoints" / f"{name}.json", record)
            if checkpoint:
                checkpoint(name, record)

        all_units, all_relationships, sections, limitations = [], [], [], []
        coverage = set()

        def extract_window(window, name, index, depth=0):
            nonlocal completed_windows
            self._check_cancelled()
            expected = {snippet.id for snippet in window}
            split = load(name + "_split")
            if split:
                adaptive_events.append(split["event"])
                midpoint = len(window) // 2
                extract_window(window[:midpoint], name + "a", index, depth + 1)
                extract_window(window[max(0, midpoint - 1):], name + "b", index, depth + 1)
                return
            cached = load(name)
            expected = {s.id for s in window}
            if cached is not None:
                extraction = Extraction.model_validate(cached)
                if {sid for section in extraction.sections for sid in section.snippet_ids} != expected:
                    raise PipelineError("Saved source analysis does not match this window. Start a new generation to protect complete source coverage.")
                if any(sid not in expected for item in [*extraction.units, *extraction.relationships] for e in item.evidence for sid in e.snippet_ids):
                    raise PipelineError("Saved evidence belongs to a different source window. Start a new generation.")
                validate_grounding(source, extraction.units, extraction.relationships)
            else:
                def validate_extraction(value):
                    if len(value.units) > self.profile.maximum_units:
                        raise ValueError("Extraction exceeds this model profile unit limit")
                    positions = {snippet.id: pos for pos, snippet in enumerate(window)}
                    for section in value.sections:
                        if section.range_end:
                            if len(section.snippet_ids) != 1 or section.snippet_ids[0] not in positions or section.range_end not in positions:
                                raise ValueError("A section range needs one first ID and one last ID in this window")
                            first, last = positions[section.snippet_ids[0]], positions[section.range_end]
                            if last < first:
                                raise ValueError("Source section range is reversed")
                            section.snippet_ids = [snippet.id for snippet in window[first:last + 1]]
                            section.range_end = ""
                    referenced = {sid for section in value.sections for sid in section.snippet_ids}
                    if referenced != expected:
                        raise ValueError("Every source snippet in this window must belong to a section, without outside snippets")
                    if any(sid not in expected for item in [*value.units, *value.relationships] for e in item.evidence for sid in e.snippet_ids):
                        raise ValueError("Evidence must cite this window's source IDs")
                    validate_grounding(source, value.units, value.relationships)
                    namespace_extraction(value, name)
                try:
                    extraction = self._request("extraction", Extraction,
                        {"preferences": preferences, "window_index": index, "source_title": source.title,
                         "source_metadata": {"timestamps_preserved": any(s.start is not None for s in source.snippets), "speaker_labels_available": any(s.speaker for s in source.snippets)},
                         "snippets": [semantic_snippet(s) for s in window]},
                        f"Extract coherent semantic sections and useful knowledge units. Prefer contiguous section ranges: snippet_ids=[first ID], range_end=last ID; Python expands exact original IDs. Every source snippet must belong to a section. Preserve main claims, mechanisms, examples, evidence, contradictions, important numbers, prerequisites, and caveats. Extract each distinct substantive idea once, however long or short this window is: the number of units follows the content, not the window length. Do not create units for greetings, small talk, sponsor reads, or restatements of an idea already extracted in this window; a window without substantive ideas has no units. Up to {self.profile.maximum_units} units for this task. Preserve significant examples, qualifications and disagreements. Label every section's role and depth by its content, never by its length or speaking style. Keep summaries to 1-2 sentences. Size each explanation to its idea: one sentence for a simple point, up to 8 sentences for a mechanism, procedure or argument, keeping every number, unit, condition and named method the source gives for it. Every significant clause in title, summary, explanation needs appropriate source evidence; quote whole relevant sentences with contiguous IDs rather than disconnected caption fragments. Use local unique unit and relationship IDs. Child IDs are empty. Explanations use selected output language, original technical terms retained. Timing is preserved separately; do not claim source timestamps are absent because these semantic inputs omit them. Do not pad with generic ideas.",
                        work_dir, validate_extraction)
                except (ProviderError, PipelineError) as error:
                    diagnostics = getattr(error, "diagnostics", {})
                    eligible = (isinstance(error, ProviderError) and error.code == "invalid_output") or (
                        isinstance(error, PipelineError) and diagnostics.get("stage") == "extraction")
                    midpoint = len(window) // 2
                    halves = [window[:midpoint], window[max(0, midpoint - 1):]]
                    sizes = [sum(len(json.dumps(semantic_snippet(item), ensure_ascii=False)) + 2
                                 for item in half) for half in halves]
                    if (not eligible or not self.profile.adaptive or depth >= self.profile.maximum_split_depth
                            or midpoint < 2 or min(sizes) < self.profile.minimum_split_characters):
                        raise
                    reason = "output_limit" if diagnostics.get("finish_reason") == "length" else "invalid_output"
                    event = {"window": name, "depth": depth, "reason": reason,
                             "source_snippets": len(window), "child_sizes": sizes}
                    adaptive_events.append(event)
                    save(name + "_split", {"split": True, "event": event})
                    self._notify("analyzing", "This model needs a smaller task. Splitting this section; completed work stays saved.")
                    extract_window(halves[0], name + "a", index, depth + 1)
                    extract_window(halves[1], name + "b", index, depth + 1)
                    return
                extraction.limitations.extend(self._review(source, extraction.units, extraction.relationships, work_dir, expected))
                save(name, extraction.model_dump(mode="json"))
            all_units.extend(extraction.units)
            all_relationships.extend(extraction.relationships)
            sections.extend(extraction.sections)
            limitations.extend(extraction.limitations)
            coverage.update(expected)
            completed_windows += 1

        for index, window in enumerate(windows):
            self._notify("analyzing", f"Analyzing source section {index + 1} of {len(windows)}", completed=index, total=len(windows))
            extract_window(window, f"extraction_{index:04d}", index)
        if not all_units:
            raise PipelineError("No substantive ideas were found in this source. Its sections are saved for review.")
        self._notify("analyzing", "Connecting ideas across the complete source", completed=len(windows), total=len(windows))
        # Level 0 synthesizes each contiguous chapter on its own. Restatements merge and
        # distinct ideas stay apart, so a chapter keeps as many key ideas as its content
        # holds, one level below the overview. Higher levels only build the overview.
        chapter_sections = split_sections(source, sections)
        chapter_units = assign_units(source, chapter_sections, all_units)
        chapter_key_ideas = [[] for _ in chapter_sections]
        chapter_titles = ["" for _ in chapter_sections]
        frontier = list(all_units)
        budget = self._budget(Synthesis.model_json_schema(), "synthesis")
        final = None
        for level in range(12):
            if level == 0:
                groups, group_chapters = [], []
                for chapter_index, members in enumerate(chapter_units):
                    for group in self._group_units(source, members, all_relationships, preferences, budget):
                        groups.append(group)
                        group_chapters.append(chapter_index)
            else:
                groups = self._group_units(source, frontier, all_relationships, preferences, budget)
            next_frontier = []
            for group_index, group in enumerate(groups):
                self._notify("analyzing", f"Connecting idea group {group_index + 1} of {len(groups)}", completed=group_index, total=len(groups))
                name = f"synthesis_{level:02d}_{group_index:04d}"
                cached = load(name)
                if cached is not None:
                    synthesis = Synthesis.model_validate(cached)
                    validate_grounding(source, synthesis.units, synthesis.relationships)
                else:
                    inputs = {u.id for u in group}
                    if level == 0:
                        max_nodes = min(8, len(group))
                        scope = ("These units come from one contiguous chapter of the source. Create one parent idea per distinct "
                                 "substantive idea: merge restatements and closely related points, keep distinct mechanisms, "
                                 "examples, numbers and objections apart. Give group_title a short chapter title. ")
                    else:
                        max_nodes = min(8, max(1, len(group) // 2)) if len(groups) > 1 else min(8, len(group))
                        scope = ""
                    def validate_synthesis(value):
                        if len(value.units) > max_nodes:
                            raise ValueError(f"This grouping may contain at most {max_nodes} parent ideas")
                        children = {cid for u in value.units for cid in u.child_ids}
                        if children != inputs:
                            raise ValueError("Parent child_ids must cover every supplied input unit and no others")
                        mapping = {u.id: f"s{level:02d}g{group_index:04d}_{u.id}" for u in value.units}
                        if len(mapping) != len(value.units) or set(mapping) & inputs:
                            raise ValueError("New parent IDs must be unique and separate from input IDs")
                        for unit in value.units:
                            unit.id = mapping[unit.id]
                        endpoints = set(mapping.values()) | inputs
                        for rel in value.relationships:
                            rel.id = f"s{level:02d}g{group_index:04d}_{rel.id}"
                            rel.source, rel.target = mapping.get(rel.source, rel.source), mapping.get(rel.target, rel.target)
                            if rel.source not in endpoints or rel.target not in endpoints:
                                raise ValueError("Synthesis relationship endpoint is unknown")
                        validate_grounding(source, value.units, value.relationships)
                        if not value.main_conclusion_evidence:
                            raise ValueError("The main conclusion needs its own original source evidence")
                        validate_grounding(source, [SimpleNamespace(id="main_conclusion", evidence=value.main_conclusion_evidence)], [])
                    synthesis = self._request("synthesis", Synthesis,
                        self._synthesis_body(source, group, all_relationships, preferences),
                        scope + f"Synthesize at most {max_nodes} coherent parent ideas, with useful cross-topic connections. EVERY supplied unit ID must be retained under one or more parent child_ids. Do not return existing units. Main question and conclusion must preserve disagreement and uncertainty. The main_conclusion_evidence must quote original passages supporting every significant clause in the main conclusion; don't assume node citations support the headline. Cite original passages for each sourced parent and each relationship. Do not turn temporal sequence into causality. Selected output language applies to all explanations.",
                        work_dir, validate_synthesis)
                    synthesis.limitations.extend(self._review(source, synthesis.units, synthesis.relationships, work_dir))
                    save(name, synthesis.model_dump(mode="json"))
                next_frontier.extend(synthesis.units)
                all_units.extend(synthesis.units)
                all_relationships.extend(synthesis.relationships)
                limitations.extend(synthesis.limitations)
                if level == 0:
                    chapter = group_chapters[group_index]
                    chapter_key_ideas[chapter].extend(u.id for u in synthesis.units)
                    chapter_titles[chapter] = chapter_titles[chapter] or synthesis.group_title
                if len(groups) == 1:
                    final = synthesis
            if final is not None:
                break
            # Chapter synthesis may keep every distinct idea; the overview levels must reduce.
            if level > 0 and len(next_frontier) >= len(frontier):
                raise PipelineError("Synthesis did not reduce context. Saved detail is available for retry.")
            frontier = next_frontier
        if final is None:
            raise PipelineError("The source requires more synthesis levels than the configured limit.")
        # The prominent headline is a claim too. Review it rather than relying
        # only on the accuracy of separately rendered nodes and arrows.
        headline_review = load("headline_review")
        if headline_review is None:
            headline_item = SimpleNamespace(evidence=final.main_conclusion_evidence)
            passages = self._original_context(source, [headline_item])
            body = {"items": [{"id": "main_conclusion", "text": final.main_conclusion}],
                    "original_passages": passages}
            if len(json.dumps(body, ensure_ascii=False)) > self._budget(GroundingReview.model_json_schema(), "grounding"):
                headline_review = {"issues": [{"item_id": "main_conclusion", "verdict": "unsupported",
                    "reason": "The complete headline evidence could not fit in one review; inspect the underlying source-grounded ideas."}], "limitations": []}
            else:
                def validate_headline(value):
                    if any(issue.item_id != "main_conclusion" for issue in value.issues):
                        raise ValueError("Headline review references an unknown item")
                review = self._request("grounding", GroundingReview, body,
                    "Review the prominent main conclusion against these cited original passages. Report concrete unsupported, exaggerated, contradicted, or missing-caveat claims. Preserve uncertainty and speaker attribution. Do not use outside knowledge. Reasons use the conclusion's language. The review cannot prove that every topic in the transcript was retained.",
                    work_dir, validate_headline)
                headline_review = review.model_dump(mode="json")
            save("headline_review", headline_review)
        headline_caveats = [issue["reason"] for issue in headline_review["issues"]]
        limitations.extend(headline_review["limitations"])
        if not source.video_id:
            limitations.append("Original video timestamp navigation is unavailable for this imported source.")
        if any(s.start is None for s in source.snippets):
            limitations.append("Some source passages have no verified timestamp.")
        limitations.append("Source grounding was checked against the supplied transcript; speaker claims were not externally fact-checked.")
        chapters = []
        for index, group in enumerate(chapter_sections):
            depth, share = chapter_profile(group)
            leaves = [u for u in chapter_units[index] if not u.child_ids]
            chapters.append(Chapter(id=f"chapter_{index + 1:02d}", title=(chapter_titles[index] or group[0].title)[:250],
                section_ids=[s.id for s in group], unit_ids=chapter_key_ideas[index], depth=depth,
                substantive_share=round(share, 3), detail=detail_level(depth, share, leaves, preferences["knowledge_level"])))
        knowledge = KnowledgeModel(source_id=source.source_id, language=language,
            main_question=final.main_question, main_conclusion=final.main_conclusion,
            main_conclusion_status="uncertain" if headline_caveats else "source",
            main_conclusion_caveats=headline_caveats,
            main_conclusion_evidence=final.main_conclusion_evidence,
            overview_ids=[u.id for u in final.units], units=all_units, relationships=all_relationships,
            sections=sections, chapters=chapters, source_coverage=[s.id for s in source.snippets if s.id in coverage],
            limitations=list(dict.fromkeys(limitations)), learning_goal=preferences["learning_goal"], knowledge_level=preferences["knowledge_level"])
        write_json(work_dir / "knowledge.json", knowledge.model_dump(mode="json"))
        self._notify("selecting_visuals", "Choosing visual forms for the source structure")
        presentation_checkpoint = f"presentation_r{PRESENTATION_REVISION}"
        cached = load(presentation_checkpoint)
        if cached is not None:
            presentation = PresentationPlan.model_validate(cached)
            validate_bundle(source, knowledge, presentation)
        else:
            selected_units = {u.id: u for u in final.units}
            # Supply a bounded collection of candidate detail shapes, never all source records.
            # Spread every bounded selection over the whole source: units, relationships and
            # sections are stored in source order, so their first entries cover only its opening.
            positions = source_positions(source)
            candidates = spread_by_source_position(
                [u for u in all_units if u.kind in DETAIL_KINDS and u.id not in selected_units], positions, 12)
            selected_units.update({u.id: u for u in candidates})
            selected_ids = set(selected_units)
            selected_relations = spread_by_source_position(
                [r for r in all_relationships if r.source in selected_ids and r.target in selected_ids], positions, 40)
            body = {"main_question": knowledge.main_question, "overview_ids": knowledge.overview_ids,
                    "units": [{"id": u.id, "title": u.title, "summary": u.summary, "kind": u.kind, "status": u.status} for u in selected_units.values()],
                    "relationships": [{"id": r.id, "source": r.source, "target": r.target, "label": r.label, "kind": r.kind, "status": r.status} for r in selected_relations],
                    "sections": [{"id": s.id, "title": s.title} for s in evenly_spaced(sections, 40)], "language": language}
            presentation = self._request("presentation", PresentationPlan, body,
                "Select 2–3 complementary useful visual forms when justified, or one for a small source. First visual should orient around major ideas; source timeline can be an additional view. Choose forms from the knowledge structure. Use only supplied node/relationship/section IDs, with relationship endpoints included. Causal graph only for source/inference causes. Titles/questions use selected output language. Do not add content or decorative graphs.",
                work_dir, lambda value: validate_bundle(source, knowledge, value))
            save(presentation_checkpoint, presentation.model_dump(mode="json"))
        write_json(work_dir / "presentation.json", presentation.model_dump(mode="json"))
        figures = self._figures(source, knowledge, preferences, work_dir, load, save)
        lecture = None
        if output_format == "lecture":
            lecture = self._lecture(source, knowledge, preferences, work_dir, load, save)
            self._notify("rendering", "Saving the lecture slides")
            self._check_cancelled()
            page_path = render_lecture(source, knowledge, lecture, work_dir / "lecture.html", figures)
        else:
            self._notify("rendering", "Saving the interactive learning page")
            self._check_cancelled()
            page_path = render_page(source, knowledge, presentation, work_dir / "page.html", figures)
        record = {"schema_version": SCHEMA_VERSION, "skill_version": SKILL_VERSION,
            "pipeline_revision": PIPELINE_REVISION, "presentation_revision": PRESENTATION_REVISION,
            "output_format": output_format,
            "lecture_revision": LECTURE_REVISION if lecture else None,
            "lecture_slides": sum(len(part.slides) for part in lecture.parts) if lecture else None,
            "figure_revision": FIGURE_REVISION, "figures": [figure.type for figure in figures.figures],
            "analysis_windows": completed_windows,
            "initial_analysis_windows": len(windows), "model_profile": self.profile.as_dict(),
            "adaptive_events": adaptive_events,
            "reasoning_effort": getattr(self.provider, "reasoning_effort", "provider default"),
            "provider": getattr(self.provider, "name", "unknown"), "model": getattr(self.provider, "model", "default"),
            "source_hash": source.content_hash, "original_source_hash": original.content_hash,
            "preferences": preferences, "fingerprint": fingerprint, "duration_seconds": round(monotonic() - started, 3),
            "usage": self.usage, "usage_scope": "current invocation only; usage from earlier cached stages is excluded",
            "cached_stages": sorted(cached_stages), "request_sizes": self.call_sizes, "source_snippets": len(source.snippets),
            "covered_snippets": len(coverage), "display_metrics": display_metrics(source, knowledge, presentation),
            "limitations": knowledge.limitations}
        write_json(work_dir / "generation.json", record)
        return {"title": source.title, "summary": knowledge.main_conclusion, "source_id": source.source_id,
                "knowledge_path": str(work_dir / "knowledge.json"), "presentation_path": str(work_dir / "presentation.json"),
                "source_path": str(work_dir / "source.json"), "page_path": str(page_path), "output_format": output_format,
                "generation_path": str(work_dir / "generation.json"), "warnings": knowledge.limitations}
