"""Versioned, provider-independent source, knowledge, and presentation contracts."""

from __future__ import annotations

import hashlib
import json
import re
from types import SimpleNamespace
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "1.0"
SKILL_VERSION = "1.0.0"


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Snippet(Contract):
    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    start: float | None = Field(default=None, ge=0)
    end: float | None = Field(default=None, ge=0)
    duration: float | None = Field(default=None, ge=0)
    timing_basis: Literal["caption", "speech", "unknown"] = "unknown"
    speaker: str | None = None

    @model_validator(mode="after")
    def valid_time(self):
        if self.start is None and (self.end is not None or self.duration is not None):
            raise ValueError("A timed snippet needs a start time")
        if self.start is not None:
            if self.end is None and self.duration is not None:
                self.end = self.start + self.duration
            if self.end is not None and self.end < self.start:
                raise ValueError("Snippet end precedes start")
        return self


class Transcript(Contract):
    schema_version: str = SCHEMA_VERSION
    source_id: str
    video_id: str | None = None
    url: str | None = None
    title: str = "Imported transcript"
    language: str = "unknown"
    origin: str = "import"
    snippets: list[Snippet] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    retrieved_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    content_hash: str = ""

    @model_validator(mode="after")
    def valid_source(self):
        ids = [s.id for s in self.snippets]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate source snippet IDs")
        if self.video_id and not re.fullmatch(r"[A-Za-z0-9_-]{11}", self.video_id):
            raise ValueError("Invalid YouTube video ID")
        payload = [{"id": s.id, "text": s.text, "start": s.start, "end": s.end} for s in self.snippets]
        actual_hash = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        if self.content_hash and self.content_hash != actual_hash:
            raise ValueError("Transcript content hash does not match its snippets")
        self.content_hash = actual_hash
        return self


class Evidence(Contract):
    snippet_ids: list[str] = Field(min_length=1, max_length=12)
    quote: str = Field(min_length=1, max_length=1800)


GroundingStatus = Literal["source", "inference", "background", "uncertain"]


class KnowledgeUnit(Contract):
    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=180)
    summary: str = Field(min_length=1, max_length=900)
    explanation: str = Field(default="", max_length=4000)
    kind: Literal["concept", "claim", "mechanism", "example", "evidence", "objection", "choice", "prerequisite", "step"] = "concept"
    status: GroundingStatus = "source"
    evidence: list[Evidence] = Field(default_factory=list, max_length=6)
    caveats: list[str] = Field(default_factory=list)
    technical_terms: list[str] = Field(default_factory=list, max_length=15)
    child_ids: list[str] = Field(default_factory=list)
    needs_visual: bool = False

    @model_validator(mode="after")
    def grounded_claim(self):
        if self.status in ("source", "inference") and not self.evidence:
            raise ValueError("Source claims and inferences require original evidence")
        if self.status == "background" and self.evidence:
            raise ValueError("Background must not inherit transcript evidence")
        return self


class Relationship(Contract):
    id: str = Field(min_length=1, max_length=100)
    source: str = Field(min_length=1, max_length=100)
    target: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=180)
    kind: Literal["causes", "depends_on", "supports", "opposes", "precedes", "part_of", "relates_to", "compares"] = "relates_to"
    explanation: str = Field(default="", max_length=1500)
    status: GroundingStatus = "source"
    evidence: list[Evidence] = Field(default_factory=list, max_length=6)
    caveats: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def grounded_connection(self):
        if self.source == self.target:
            raise ValueError("A relationship must connect different units")
        if self.status in ("source", "inference") and not self.evidence:
            raise ValueError("A source relationship or inference needs evidence")
        if self.status == "background" and self.evidence:
            raise ValueError("Background relationships cannot cite transcript as evidence")
        return self


class SourceSection(Contract):
    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=250)
    snippet_ids: list[str] = Field(min_length=1)
    unit_ids: list[str] = Field(default_factory=list)


class ExtractedSection(SourceSection):
    range_end: str = Field(default="", description="To describe a contiguous section efficiently, snippet_ids contains its first source ID and range_end its last source ID. Empty range_end means explicit snippet_ids.")


class Extraction(Contract):
    units: list[KnowledgeUnit] = Field(min_length=1, max_length=80)
    relationships: list[Relationship] = Field(default_factory=list, max_length=120)
    sections: list[ExtractedSection] = Field(min_length=1, max_length=48)
    limitations: list[str] = Field(default_factory=list)


class Synthesis(Contract):
    main_question: str = Field(min_length=1, max_length=700)
    main_conclusion: str = Field(min_length=1, max_length=1400)
    main_conclusion_evidence: list[Evidence] = Field(default_factory=list, max_length=12)
    units: list[KnowledgeUnit] = Field(min_length=1, max_length=8)
    relationships: list[Relationship] = Field(default_factory=list, max_length=20)
    limitations: list[str] = Field(default_factory=list)


class GroundingIssue(Contract):
    item_id: str
    verdict: Literal["unsupported", "overstated", "contradicted", "missing_caveat"]
    reason: str


class GroundingReview(Contract):
    issues: list[GroundingIssue] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class GroundingCorrections(Contract):
    units: list[KnowledgeUnit] = Field(default_factory=list, max_length=20)
    relationships: list[Relationship] = Field(default_factory=list, max_length=30)


class KnowledgeModel(Contract):
    schema_version: str = SCHEMA_VERSION
    source_id: str
    language: Literal["vi", "en"]
    main_question: str
    main_conclusion: str
    main_conclusion_status: GroundingStatus = "source"
    main_conclusion_caveats: list[str] = Field(default_factory=list)
    main_conclusion_evidence: list[Evidence] = Field(default_factory=list)
    overview_ids: list[str] = Field(min_length=1, max_length=8)
    units: list[KnowledgeUnit] = Field(min_length=1)
    relationships: list[Relationship] = Field(default_factory=list)
    sections: list[SourceSection] = Field(default_factory=list)
    source_coverage: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    learning_goal: str = ""
    knowledge_level: str = "balanced"

    @model_validator(mode="after")
    def references(self):
        ids = [u.id for u in self.units]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate knowledge unit IDs")
        valid = set(ids)
        if len(self.overview_ids) != len(set(self.overview_ids)):
            raise ValueError("Duplicate overview units")
        if len({s.id for s in self.sections}) != len(self.sections):
            raise ValueError("Duplicate source section IDs")
        if not set(self.overview_ids) <= valid:
            raise ValueError("Unknown overview unit")
        relationship_ids = [r.id for r in self.relationships]
        if len(relationship_ids) != len(set(relationship_ids)):
            raise ValueError("Duplicate relationship IDs")
        for unit in self.units:
            if not set(unit.child_ids) <= valid or unit.id in unit.child_ids:
                raise ValueError(f"Unknown or self-referencing children for {unit.id}")
        for rel in self.relationships:
            if rel.source not in valid or rel.target not in valid:
                raise ValueError(f"Unknown relationship endpoint for {rel.id}")
        for section in self.sections:
            if not set(section.unit_ids) <= valid:
                raise ValueError("Unknown section units")
        # Disclosure must terminate even if a provider accidentally creates a cycle.
        graph = {u.id: u.child_ids for u in self.units}
        visited, active = set(), set()
        def visit(node):
            if node in active:
                raise ValueError("Cycle in knowledge disclosure hierarchy")
            if node in visited:
                return
            active.add(node)
            for child in graph[node]:
                visit(child)
            active.remove(node)
            visited.add(node)
        for node in graph:
            visit(node)
        return self


class Visual(Contract):
    id: str
    type: Literal["concept_map", "causal_graph", "process", "argument_map", "timeline", "hierarchy", "comparison"]
    title: str
    reader_question: str
    rationale: str
    node_ids: list[str] = Field(default_factory=list, max_length=12)
    relationship_ids: list[str] = Field(default_factory=list, max_length=24)
    section_ids: list[str] = Field(default_factory=list)


class PresentationPlan(Contract):
    schema_version: str = SCHEMA_VERSION
    visuals: list[Visual] = Field(min_length=1, max_length=3)
    reading_order: list[str] = Field(default_factory=list)


def normalize_quote(text: str) -> str:
    return " ".join(text.split()).casefold()


def validate_grounding(source: Transcript, units: list[KnowledgeUnit], relationships: list[Relationship]) -> None:
    snippets = {s.id: s for s in source.snippets}
    positions = {s.id: index for index, s in enumerate(source.snippets)}
    for item in [*units, *relationships]:
        for evidence in item.evidence:
            if any(sid not in snippets for sid in evidence.snippet_ids):
                raise ValueError(f"{item.id} references missing source snippets")
            indices = [positions[sid] for sid in evidence.snippet_ids]
            if indices != list(range(indices[0], indices[0] + len(indices))):
                raise ValueError(f"{item.id} evidence must cite a contiguous source span in original order")
            original = " ".join(snippets[sid].text for sid in evidence.snippet_ids)
            if normalize_quote(evidence.quote) not in normalize_quote(original):
                raise ValueError(f"{item.id} quote is not present in its original source span")


def validate_bundle(source: Transcript, knowledge: KnowledgeModel, presentation: PresentationPlan) -> None:
    if source.source_id != knowledge.source_id:
        raise ValueError("Knowledge belongs to a different source")
    valid_snippets = {s.id for s in source.snippets}
    if set(knowledge.source_coverage) != valid_snippets:
        raise ValueError("Knowledge source coverage is incomplete")
    validate_grounding(source, knowledge.units, knowledge.relationships)
    validate_grounding(source, [SimpleNamespace(id="main_conclusion", evidence=knowledge.main_conclusion_evidence)], [])
    unit_ids = {u.id for u in knowledge.units}
    rel_ids = {r.id for r in knowledge.relationships}
    section_ids = {s.id for s in knowledge.sections}
    for section in knowledge.sections:
        if not set(section.snippet_ids) <= valid_snippets:
            raise ValueError("Section references unknown snippets")
    if knowledge.sections and {sid for section in knowledge.sections for sid in section.snippet_ids} != valid_snippets:
        raise ValueError("Source sections do not cover the complete transcript")
    for visual in presentation.visuals:
        if not set(visual.node_ids) <= unit_ids or not set(visual.relationship_ids) <= rel_ids or not set(visual.section_ids) <= section_ids:
            raise ValueError("Presentation references unknown knowledge")
        if len(set(visual.node_ids)) != len(visual.node_ids) or len(set(visual.relationship_ids)) != len(visual.relationship_ids):
            raise ValueError("Visual references must be unique")
        if visual.type == "timeline":
            if not visual.section_ids and not knowledge.sections:
                raise ValueError("Timeline needs source sections")
        elif not visual.node_ids:
            raise ValueError("A knowledge visual needs at least one node")
        visual_nodes = set(visual.node_ids)
        if any(r.id in visual.relationship_ids and (r.source not in visual_nodes or r.target not in visual_nodes) for r in knowledge.relationships):
            raise ValueError("Visual relationship endpoints must be displayed in that visual")
        if visual.type == "causal_graph":
            selected = [r for r in knowledge.relationships if r.id in visual.relationship_ids]
            if not selected or any(r.kind != "causes" or r.status not in ("source", "inference") for r in selected):
                raise ValueError("Causal graph requires explicitly grounded or labelled inferred causes")
    ids = [v.id for v in presentation.visuals]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate visual IDs")
    if presentation.reading_order and (len(presentation.reading_order) != len(ids) or set(presentation.reading_order) != set(ids)):
        raise ValueError("Reading order must contain each visual exactly once")
