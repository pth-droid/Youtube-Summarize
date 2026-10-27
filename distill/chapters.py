"""Deterministic chapters: duration sets how many there are, content sets how much each shows."""

from __future__ import annotations

from bisect import bisect_right

# Leaf ideas shown inline under each chapter key idea, per detail level. The renderer
# embeds this table in the page, so the reader and the Python metrics agree.
NOTE_LEAF_LIMITS = {"brief": 0, "standard": 3, "detailed": 12}
LEVELS = ("brief", "standard", "detailed")
TECHNICAL_KINDS = ("mechanism", "evidence", "step", "prerequisite")
MINUTES_PER_CHAPTER = 8
CHARACTERS_PER_CHAPTER = 7500  # About eight minutes of captioned speech, for untimed imports.
MAXIMUM_CHAPTERS = 12
# Below this share of substantive passages a chapter is mostly talk, sponsor reads or recap.
MINIMUM_SUBSTANCE = 0.35


def chapter_count(source) -> int:
    """Chapters are navigation; their number follows duration, never the depth shown."""
    times = [value for snippet in source.snippets for value in (snippet.end, snippet.start) if value is not None]
    if times:
        estimate = max(times) / 60 / MINUTES_PER_CHAPTER
    else:
        estimate = sum(len(snippet.text) for snippet in source.snippets) / CHARACTERS_PER_CHAPTER
    return max(1, min(MAXIMUM_CHAPTERS, round(estimate)))


def split_sections(source, sections) -> list[list]:
    """Group semantic sections into contiguous chapters of similar source span."""
    if not sections:
        return []
    positions = {snippet.id: index for index, snippet in enumerate(source.snippets)}
    start = lambda section: min(positions[sid] for sid in section.snippet_ids)
    count = chapter_count(source)
    buckets = [[] for _ in range(count)]
    for section in sorted(sections, key=start):
        buckets[min(count - 1, start(section) * count // len(source.snippets))].append(section)
    return [bucket for bucket in buckets if bucket]


def assign_units(source, chapter_sections, units) -> list[list]:
    """Place each unit in the chapter where its evidence starts, keeping source order."""
    if not chapter_sections:
        return []
    positions = {snippet.id: index for index, snippet in enumerate(source.snippets)}
    starts = [min(positions[sid] for section in group for sid in section.snippet_ids) for group in chapter_sections]
    listed = {uid: index for index, group in enumerate(chapter_sections) for section in group for uid in section.unit_ids}
    result, current = [[] for _ in chapter_sections], 0
    for unit in units:
        cited = [positions[sid] for evidence in unit.evidence for sid in evidence.snippet_ids if sid in positions]
        if cited:
            current = max(0, bisect_right(starts, min(cited)) - 1)
        elif unit.id in listed:
            current = listed[unit.id]
        # Uncited background stays beside the preceding unit.
        result[current].append(unit)
    return result


def chapter_profile(sections) -> tuple[str, float]:
    """Depth and substantive share of a chapter, weighted by passage count.

    Depth leans towards preserving detail: an expert third of the substantive
    material makes the chapter expert, even when the rest is introductory.
    """
    sizes = {section.id: len(section.snippet_ids) for section in sections}
    total = sum(sizes.values()) or 1
    substantive = [section for section in sections if section.role == "substantive"]
    weight = sum(sizes[section.id] for section in substantive)
    share = weight / total
    if not weight:
        return "basic", share
    expert = sum(sizes[s.id] for s in substantive if s.depth == "expert") / weight
    intermediate = sum(sizes[s.id] for s in substantive if s.depth == "intermediate") / weight
    if expert >= 1 / 3:
        return "expert", share
    if expert + intermediate >= 1 / 2:
        return "intermediate", share
    return "basic", share


def detail_level(depth: str, substantive_share: float, leaves, knowledge_level: str = "balanced") -> str:
    """How much a chapter shows by default; the reader can still switch every chapter."""
    if substantive_share < MINIMUM_SUBSTANCE:
        return "brief"
    level = {"basic": 0, "intermediate": 1, "expert": 2}[depth]
    if level == 1 and leaves and sum(unit.kind in TECHNICAL_KINDS for unit in leaves) / len(leaves) >= 0.5:
        level = 2
    if knowledge_level == "advanced":
        level = min(2, level + 1)
    return LEVELS[level]
