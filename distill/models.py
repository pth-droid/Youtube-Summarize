"""Versioned, provider-independent source, knowledge, and presentation contracts."""

from __future__ import annotations

import hashlib
import json
import re
from types import SimpleNamespace
from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "1.1"
SKILL_VERSION = "1.1.0"


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


SectionRole = Literal["substantive", "anecdote", "banter", "sponsor", "recap"]
ContentDepth = Literal["basic", "intermediate", "expert"]
DetailLevel = Literal["brief", "standard", "detailed"]


class SourceSection(Contract):
    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=250)
    snippet_ids: list[str] = Field(min_length=1)
    unit_ids: list[str] = Field(default_factory=list)
    role: SectionRole = Field(default="substantive", description="What this passage does, judged by content: substantive ideas, an illustrative anecdote or tangent, greetings/small talk/intro/outro, a sponsor read, or a recap of earlier points.")
    depth: ContentDepth = Field(default="intermediate", description="How specialised the content is, regardless of length or speaking style: basic (general-audience explanation), intermediate (domain mechanisms, tradeoffs, procedures), expert (specialist detail, data, formal reasoning).")


class ExtractedSection(SourceSection):
    range_end: str = Field(default="", description="To describe a contiguous section efficiently, snippet_ids contains its first source ID and range_end its last source ID. Empty range_end means explicit snippet_ids.")


class Extraction(Contract):
    # A window of greetings or small talk legitimately contains no knowledge units.
    units: list[KnowledgeUnit] = Field(default_factory=list, max_length=80)
    relationships: list[Relationship] = Field(default_factory=list, max_length=120)
    sections: list[ExtractedSection] = Field(min_length=1, max_length=48)
    limitations: list[str] = Field(default_factory=list)


class Synthesis(Contract):
    group_title: str = Field(default="", max_length=180, description="A short title naming what this group of ideas covers, such as a chapter title.")
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


class Chapter(Contract):
    """A contiguous part of the source and its key ideas, sized by content rather than duration."""
    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=250)
    section_ids: list[str] = Field(min_length=1)
    unit_ids: list[str] = Field(default_factory=list)
    depth: ContentDepth = "intermediate"
    substantive_share: float = Field(default=1.0, ge=0, le=1)
    detail: DetailLevel = "standard"


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
    chapters: list[Chapter] = Field(default_factory=list)
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
        section_ids = {s.id for s in self.sections}
        if len({c.id for c in self.chapters}) != len(self.chapters):
            raise ValueError("Duplicate chapter IDs")
        for chapter in self.chapters:
            if not set(chapter.section_ids) <= section_ids or not set(chapter.unit_ids) <= valid:
                raise ValueError(f"Unknown sections or units in chapter {chapter.id}")
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


SlideText = Annotated[str, Field(min_length=1, max_length=260)]


class LectureColumn(Contract):
    heading: str = Field(min_length=1, max_length=120)
    points: list[SlideText] = Field(min_length=1, max_length=5)


class LectureEntry(Contract):
    label: str = Field(min_length=1, max_length=40, description="A short label: a time, temperature, stage or level name. On stats slides, the figure exactly as the ideas state it, such as 9 bar or 18–22%.")
    text: SlideText


LAYOUT_HELP = ("points: key ideas as short bullets. steps: an ordered procedure. compare: exactly two columns contrasting two options. "
               "columns: two to four parallel categories, each a heading with short points. table: two to four columns with the same "
               "number of rows, read across like a table. timeline: two to six ordered moments, each a short label (time, temperature, "
               "stage) and its text. pyramid: three to five levels from the narrow top to the broad foundation. funnel: three to five "
               "stages that narrow from first to last. stats: two to four figures the ideas state, each with what it means. quote: the "
               "app shows an original passage cited by the slide's ideas verbatim; points explain it.")
# Layouts that use entries, with how many each holds.
ENTRY_LAYOUTS = {"timeline": (2, 6), "pyramid": (3, 5), "funnel": (3, 5), "stats": (2, 4)}


class LectureSlide(Contract):
    layout: Literal["points", "steps", "compare", "columns", "table", "timeline", "pyramid", "funnel", "stats", "quote"] = Field(description=LAYOUT_HELP)
    title: str = Field(min_length=1, max_length=140)
    points: list[SlideText] = Field(default_factory=list, max_length=6, description="Short slide bullets, not full paragraphs. points, steps and quote slides only; empty otherwise.")
    columns: list[LectureColumn] = Field(default_factory=list, max_length=4, description="compare: exactly two columns. columns and table: two to four. Empty otherwise.")
    entries: list[LectureEntry] = Field(default_factory=list, max_length=6, description="timeline, pyramid, funnel and stats slides only; empty otherwise.")
    unit_ids: list[str] = Field(min_length=1, max_length=6, description="Supplied idea IDs this slide teaches. The slide text stays within these ideas.")
    notes: str = Field(default="", max_length=1600, description="What the presenter says for this slide, in full sentences.")

    @model_validator(mode="after")
    def layout_content(self):
        if self.layout in ("compare", "columns", "table"):
            low, high = (2, 2) if self.layout == "compare" else (2, 4)
            if not low <= len(self.columns) <= high or self.points or self.entries:
                raise ValueError(f"A {self.layout} slide needs {'exactly two' if low == high else 'two to four'} columns and no points or entries")
            if self.layout == "table" and len({len(column.points) for column in self.columns}) != 1:
                raise ValueError("A table slide needs the same number of rows in every column")
            if self.layout == "columns" and sum(len(column.points) for column in self.columns) > 12:
                raise ValueError("A columns slide holds at most twelve points in all; split it over two slides")
        elif self.layout in ENTRY_LAYOUTS:
            low, high = ENTRY_LAYOUTS[self.layout]
            if not low <= len(self.entries) <= high or self.points or self.columns:
                raise ValueError(f"A {self.layout} slide needs {low} to {high} entries and no points or columns")
        elif self.columns or self.entries or not self.points:
            raise ValueError("points, steps and quote slides need points and no columns or entries")
        return self


def stated_numbers(text: str) -> set[str]:
    """Numbers as written, with a decimal comma read as a point, so 1,15 and 1.15 match."""
    return {match.replace(",", ".") for match in re.findall(r"\d+(?:[.,]\d+)?", text)}


def check_stats(slide: LectureSlide, units: dict) -> None:
    """Every figure on a stats slide must be a number its cited ideas state."""
    if slide.layout != "stats":
        return
    stated = set()
    for uid in slide.unit_ids:
        unit = units[uid]
        stated |= stated_numbers(" ".join([unit.title, unit.summary, unit.explanation, *(ev.quote for ev in unit.evidence)]))
    for entry in slide.entries:
        missing = stated_numbers(entry.label) - stated
        if missing or not stated_numbers(entry.label):
            raise ValueError(f"A stats figure must be a number its cited ideas state: {entry.label}")


class LecturePart(Contract):
    chapter_id: str = Field(min_length=1, max_length=100)
    slides: list[LectureSlide] = Field(min_length=1, max_length=6)


class LectureParts(Contract):
    parts: list[LecturePart] = Field(min_length=1, max_length=12)


class LectureFrame(Contract):
    title: str = Field(min_length=1, max_length=160, description="Lecture title in the output language.")
    objectives: list[Annotated[str, Field(min_length=1, max_length=240)]] = Field(min_length=2, max_length=5, description="What the audience can explain or do after the talk.")
    takeaways: list[Annotated[str, Field(min_length=1, max_length=260)]] = Field(min_length=2, max_length=6)


class LecturePlan(LectureFrame):
    schema_version: str = SCHEMA_VERSION
    parts: list[LecturePart] = Field(min_length=1)


def validate_lecture(knowledge: KnowledgeModel, lecture: LecturePlan) -> None:
    units = {u.id: u for u in knowledge.units}
    # "overview" teaches the overview ideas when no chapter has knowledge of its own.
    chapters = {c.id for c in knowledge.chapters} | {"overview"}
    for part in lecture.parts:
        if part.chapter_id not in chapters:
            raise ValueError(f"Lecture part references unknown chapter {part.chapter_id}")
        for slide in part.slides:
            if not set(slide.unit_ids) <= set(units):
                raise ValueError("A lecture slide references unknown ideas")
            if slide.layout == "quote" and not any(units[uid].evidence for uid in slide.unit_ids):
                raise ValueError("A quote slide needs an idea with original evidence")
            check_stats(slide, units)


FigureLabel = Annotated[str, Field(min_length=1, max_length=80)]
UnitRefs = Annotated[list[str], Field(min_length=1, max_length=6, description="Supplied idea IDs that establish this element.")]
Provenance = Literal["source", "background", "illustrative"]
PROVENANCE_HELP = ("source: every number is a value the supplied ideas state. background: standard reference values the source "
                   "does not state; cite the ideas they illustrate. illustrative: only the shape or arrangement carries meaning; the app "
                   "hides the numbers.")


class FigurePoint(Contract):
    x: float
    y: float


class FigureSeries(Contract):
    id: str = Field(min_length=1, max_length=40)
    label: FigureLabel
    unit: str = Field(default="", max_length=16, description="Measurement unit such as °C, °C/min, bar, ml/s or g. Series with one unit share one panel; never mix units in a series.")
    provenance: Provenance = Field(description=PROVENANCE_HELP)
    points: list[FigurePoint] = Field(min_length=2, max_length=60, description="Points in increasing x order. For source values, only the stated points; the app marks the joins between them.")
    unit_ids: UnitRefs


class FigurePhase(Contract):
    id: str = Field(min_length=1, max_length=40)
    label: FigureLabel
    start: float
    end: float
    note: str = Field(default="", max_length=280, description="What happens in this phase, in one or two sentences.")
    unit_ids: UnitRefs


class FigureEvent(Contract):
    at: float
    label: FigureLabel
    unit_ids: UnitRefs


class StateProperty(Contract):
    key: Literal["moisture", "volume", "color", "pressure", "cracks", "oil", "porosity", "dissolved", "temperature", "other"] = Field(
        description="What the property describes; the app draws known keys on the subject glyph.")
    label: FigureLabel
    level: int = Field(ge=0, le=4, description="Relative level: 0 none, 1 low, 2 medium, 3 high, 4 very high.")
    text: str = Field(default="", max_length=80, description="A short stated value or change, such as '11% → 2%'. Empty when the source gives none.")


class FigureState(Contract):
    phase_id: str = Field(min_length=1, max_length=40)
    caption: str = Field(min_length=1, max_length=280)
    properties: list[StateProperty] = Field(min_length=1, max_length=5)
    unit_ids: UnitRefs


class CompoundLane(Contract):
    name: FigureLabel
    levels: list[int] = Field(min_length=1, max_length=8, description="One relative amount from 0 to 4 for each phase, in phase order.")
    note: str = Field(default="", max_length=200)
    unit_ids: UnitRefs

    @model_validator(mode="after")
    def bounded_levels(self):
        if any(level < 0 or level > 4 for level in self.levels):
            raise ValueError("Compound levels run from 0 to 4")
        return self


class ProcessSpec(Contract):
    axis: Literal["time", "position", "other"] = Field(description="time: every x value is in seconds from the start.")
    axis_label: FigureLabel
    axis_unit: str = Field(default="", max_length=16, description="Unit for position or other axes; empty for time.")
    subject: Literal["bean", "particle", "generic"] = Field(description="Glyph for the states: a roasting coffee bean, a ground particle during extraction, or a generic body.")
    subject_label: FigureLabel
    phases: list[FigurePhase] = Field(min_length=2, max_length=8)
    events: list[FigureEvent] = Field(default_factory=list, max_length=8)
    series: list[FigureSeries] = Field(default_factory=list, max_length=6)
    states: list[FigureState] = Field(default_factory=list, max_length=8)
    compounds: list[CompoundLane] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def consistent_axis(self):
        if not (self.series or self.states or self.compounds):
            raise ValueError("A process figure needs quantity series, subject states or compound lanes; phases alone belong in the text")
        for before, after in zip(self.phases, self.phases[1:]):
            if after.start < before.end - 1e-6:
                raise ValueError("Phases must follow each other in order without overlapping")
        if any(phase.end <= phase.start for phase in self.phases):
            raise ValueError("Each phase must end after it starts")
        low, high = self.phases[0].start, self.phases[-1].end
        span = high - low
        if any(not low - span * .02 <= event.at <= high + span * .02 for event in self.events):
            raise ValueError("Events must fall inside the phase range")
        phase_ids = [phase.id for phase in self.phases]
        if len(set(phase_ids)) != len(phase_ids):
            raise ValueError("Phase IDs must be unique")
        state_ids = [state.phase_id for state in self.states]
        if len(set(state_ids)) != len(state_ids) or not set(state_ids) <= set(phase_ids):
            raise ValueError("Each state describes one supplied phase, at most once")
        if any(len(lane.levels) != len(self.phases) for lane in self.compounds):
            raise ValueError("Each compound lane needs one level per phase")
        series_ids = [series.id for series in self.series]
        if len(set(series_ids)) != len(series_ids):
            raise ValueError("Series IDs must be unique")
        panels = {}
        for series in self.series:
            xs = [point.x for point in series.points]
            if xs != sorted(xs) or len(set(xs)) != len(xs):
                raise ValueError("Series points must be in increasing x order")
            if any(not low - span * .05 <= x <= high + span * .05 for x in xs):
                raise ValueError("Series points must fall inside the phase range")
            panels.setdefault((series.unit, series.provenance == "illustrative"), []).append(series.id)
        if any(len(ids) > 3 for ids in panels.values()) or len(panels) > 3:
            raise ValueError("Use at most three panels with at most three series each")
        return self


class ApparatusPart(Contract):
    slot: str = Field(min_length=1, max_length=40, description="A slot ID of the chosen template.")
    label: FigureLabel
    note: str = Field(default="", max_length=280)
    unit_ids: list[str] = Field(default_factory=list, max_length=6)


class ApparatusFlow(Contract):
    path: str = Field(min_length=1, max_length=40, description="A path ID of the chosen template.")
    kind: Literal["conduction", "convection", "radiation", "air", "water", "gas", "pressure", "material"] = Field(
        description="One of the kinds the chosen path allows.")
    label: FigureLabel
    unit_ids: UnitRefs


class ApparatusSpec(Contract):
    template: Literal["drum_roaster", "espresso", "pour_over"]
    parts: list[ApparatusPart] = Field(min_length=1, max_length=12)
    flows: list[ApparatusFlow] = Field(default_factory=list, max_length=10)


class MapRegion(Contract):
    label: FigureLabel
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    note: str = Field(default="", max_length=280)
    emphasis: bool = Field(default=False, description="True for the one target or recommended region.")
    unit_ids: UnitRefs


class MapPoint(Contract):
    label: FigureLabel
    x: float
    y: float
    unit_ids: UnitRefs


class RegionMapSpec(Contract):
    x_label: FigureLabel
    x_unit: str = Field(default="", max_length=16)
    y_label: FigureLabel
    y_unit: str = Field(default="", max_length=16)
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    provenance: Provenance = Field(description=PROVENANCE_HELP)
    regions: list[MapRegion] = Field(min_length=1, max_length=9)
    points: list[MapPoint] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def inside_axes(self):
        if self.x_max <= self.x_min or self.y_max <= self.y_min:
            raise ValueError("Each map axis must increase")
        for item in [*self.regions, *self.points]:
            xs = (item.x_min, item.x_max) if isinstance(item, MapRegion) else (item.x, item.x)
            ys = (item.y_min, item.y_max) if isinstance(item, MapRegion) else (item.y, item.y)
            if xs[1] < xs[0] or ys[1] < ys[0]:
                raise ValueError("A region's minimum must not exceed its maximum")
            if xs[0] < self.x_min or xs[1] > self.x_max or ys[0] < self.y_min or ys[1] > self.y_max:
                raise ValueError("Regions and points must lie inside the map axes")
        if sum(region.emphasis for region in self.regions) > 1:
            raise ValueError("Emphasize at most one region")
        return self


class Lever(Contract):
    unit_id: str = Field(min_length=1, max_length=100, description="The supplied idea that names an adjustable setting or condition.")
    label: Annotated[str, Field(min_length=1, max_length=60)]


class SignedEffect(Contract):
    relationship_id: str = Field(min_length=1, max_length=100, description="A supplied 'causes' relationship.")
    direction: Literal["increases", "decreases"] = Field(description="When the relationship's source rises, its target rises (increases) or falls (decreases), as the source states.")


class WhatIfSpec(Contract):
    levers: list[Lever] = Field(min_length=1, max_length=4)
    effects: list[SignedEffect] = Field(min_length=1, max_length=12)


class ScaleLevel(Contract):
    scale: Annotated[str, Field(min_length=1, max_length=40, description="The size or scale, such as 'Drum · about 1 m' or 'Cell wall · micrometres'.")]
    title: FigureLabel
    summary: str = Field(min_length=1, max_length=280)
    unit_ids: UnitRefs


class ScaleLadderSpec(Contract):
    levels: list[ScaleLevel] = Field(min_length=2, max_length=5, description="From the largest scale to the smallest.")


FIGURE_SPECS = ("process", "apparatus", "region_map", "what_if", "scale_ladder")


class Figure(Contract):
    id: str = Field(min_length=1, max_length=40)
    type: Literal["process", "apparatus", "region_map", "what_if", "scale_ladder"] = Field(description=(
        "process: change over time or position in phases, with optional quantity curves, subject states and compound lanes. "
        "apparatus: a labelled cutaway of a roaster or brewer with heat, air, water, gas, pressure or material flows. "
        "region_map: two quantities with named regions, such as a brewing control chart. "
        "what_if: adjustable settings and the effects the source states they have. "
        "scale_ladder: the same process seen at several sizes."))
    title: str = Field(min_length=1, max_length=120)
    reader_question: str = Field(min_length=1, max_length=200)
    caption: str = Field(default="", max_length=400)
    unit_ids: list[str] = Field(min_length=1, max_length=12, description="The supplied ideas this figure teaches.")
    process: ProcessSpec | None = Field(default=None, description="Only for type process; null otherwise.")
    apparatus: ApparatusSpec | None = Field(default=None, description="Only for type apparatus; null otherwise.")
    region_map: RegionMapSpec | None = Field(default=None, description="Only for type region_map; null otherwise.")
    what_if: WhatIfSpec | None = Field(default=None, description="Only for type what_if; null otherwise.")
    scale_ladder: ScaleLadderSpec | None = Field(default=None, description="Only for type scale_ladder; null otherwise.")

    @model_validator(mode="after")
    def one_spec(self):
        present = [name for name in FIGURE_SPECS if getattr(self, name) is not None]
        if present != [self.type]:
            raise ValueError("Fill exactly the specification that matches the figure type; the others are null")
        return self


class FigureSet(Contract):
    figures: list[Figure] = Field(default_factory=list, max_length=4, description="Empty when the source has no process, apparatus or quantity that a figure would explain better than text.")


class FigurePlan(FigureSet):
    schema_version: str = SCHEMA_VERSION


def figure_unit_ids(figure: Figure) -> set[str]:
    """Every idea a figure cites, at any depth."""
    found = set(figure.unit_ids)
    def visit(value):
        if isinstance(value, BaseModel):
            for name in type(value).model_fields:
                item = getattr(value, name)
                if name == "unit_ids" and isinstance(item, list):
                    found.update(item)
                elif name == "unit_id" and isinstance(item, str):
                    found.add(item)
                else:
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
    for name in FIGURE_SPECS:
        visit(getattr(figure, name))
    return found


def validate_figures(knowledge: KnowledgeModel, plan: FigureSet, allowed_units: set[str] | None = None,
                     allowed_relationships: set[str] | None = None) -> None:
    from .apparatus import TEMPLATES

    units = {u.id: u for u in knowledge.units}
    relationships = {r.id: r for r in knowledge.relationships}
    allowed_units = set(units) if allowed_units is None else allowed_units & set(units)
    allowed_relationships = set(relationships) if allowed_relationships is None else allowed_relationships & set(relationships)
    ids = [figure.id for figure in plan.figures]
    if len(set(ids)) != len(ids):
        raise ValueError("Figure IDs must be unique")
    for figure in plan.figures:
        if not figure_unit_ids(figure) <= allowed_units:
            raise ValueError(f"Figure {figure.id} cites ideas that were not supplied")
        if figure.process:
            for series in figure.process.series:
                if series.provenance == "source" and not any(units[uid].evidence for uid in series.unit_ids):
                    raise ValueError("A series of source values needs an idea with original evidence")
        if figure.apparatus:
            template = TEMPLATES[figure.apparatus.template]
            slots = [part.slot for part in figure.apparatus.parts]
            if len(set(slots)) != len(slots) or not set(slots) <= set(template["slots"]):
                raise ValueError(f"Apparatus parts must use distinct slots of the {figure.apparatus.template} template")
            for flow in figure.apparatus.flows:
                path = template["paths"].get(flow.path)
                if path is None or flow.kind not in path["kinds"]:
                    raise ValueError(f"Flow {flow.path} must be a {figure.apparatus.template} path drawn with one of its allowed kinds")
            if len({flow.path for flow in figure.apparatus.flows}) != len(figure.apparatus.flows):
                raise ValueError("Each apparatus path carries one flow")
        if figure.what_if:
            sources = set()
            for effect in figure.what_if.effects:
                relationship = relationships.get(effect.relationship_id)
                if effect.relationship_id not in allowed_relationships or relationship is None or relationship.kind != "causes":
                    raise ValueError("What-if effects must use supplied 'causes' relationships")
                if not {relationship.source, relationship.target} <= allowed_units:
                    raise ValueError("What-if effects must connect supplied ideas")
                sources.add(relationship.source)
            if len({effect.relationship_id for effect in figure.what_if.effects}) != len(figure.what_if.effects):
                raise ValueError("Each relationship appears once in a what-if figure")
            if not {lever.unit_id for lever in figure.what_if.levers} <= sources:
                raise ValueError("Each lever must be the cause of at least one supplied effect")


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
