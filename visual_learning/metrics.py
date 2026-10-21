"""Deterministic measures of what a page shows, relative to its complete source."""

from __future__ import annotations

from typing import Any, Iterable, Sequence


def source_positions(source) -> dict[str, float]:
    """Relative position (0 to below 1) of every snippet, in source order."""
    total = len(source.snippets)
    return {snippet.id: index / total for index, snippet in enumerate(source.snippets)}


def first_cited_position(item, positions: dict[str, float]) -> float | None:
    cited = [positions[sid] for evidence in item.evidence for sid in evidence.snippet_ids if sid in positions]
    return min(cited) if cited else None


def evenly_spaced(items: Sequence, limit: int) -> list:
    """Keep order and sample across the whole sequence, not only its beginning."""
    if limit <= 0:
        return []
    if len(items) <= limit:
        return list(items)
    if limit == 1:
        return [items[0]]
    return [items[round(index * (len(items) - 1) / (limit - 1))] for index in range(limit)]


def spread_by_source_position(items: Iterable, positions: dict[str, float], limit: int) -> list:
    """Select up to `limit` items spread over the source by where their evidence starts.

    Extraction order is chronological, so taking the first matches selects only
    the opening of a long source. Items without source evidence fill remaining room.
    """
    keyed = [(first_cited_position(item, positions), item) for item in items]
    located = [item for _, item in sorted((pair for pair in keyed if pair[0] is not None), key=lambda pair: pair[0])]
    unlocated = [item for position, item in keyed if position is None]
    chosen = evenly_spaced(located, limit)
    return chosen + unlocated[:max(0, limit - len(chosen))]


def quarter_counts(items: Iterable, positions: dict[str, float]) -> list[int]:
    counts = [0, 0, 0, 0]
    for item in items:
        position = first_cited_position(item, positions)
        if position is not None:
            counts[min(3, int(position * 4))] += 1
    return counts


def dig_deeper_depths(knowledge) -> dict[str, int]:
    """Number of saved-detail levels between the overview and each unit."""
    units = {unit.id: unit for unit in knowledge.units}
    depths, frontier, depth = {}, list(knowledge.overview_ids), 0
    while frontier:
        following = []
        for uid in frontier:
            if uid in depths or uid not in units:
                continue
            depths[uid] = depth
            following.extend(units[uid].child_ids)
        frontier, depth = following, depth + 1
    return depths


def display_metrics(source, knowledge, presentation) -> dict[str, Any]:
    """Describe how much extracted detail reaches the reader, and from which part of the source.

    These are volume and placement measures. They do not judge content complexity
    or importance; a long conversational source can legitimately need little detail.
    """
    positions = source_positions(source)
    units = {unit.id: unit for unit in knowledge.units}
    leaves = [unit for unit in knowledge.units if not unit.child_ids]
    visible_ids = dict.fromkeys(nid for visual in presentation.visuals for nid in visual.node_ids)
    visible = [units[nid] for nid in visible_ids if nid in units]
    depths = dig_deeper_depths(knowledge)
    histogram: dict[str, int] = {}
    for leaf in leaves:
        key = str(depths[leaf.id]) if leaf.id in depths else "unreachable"
        histogram[key] = histogram.get(key, 0) + 1
    times = [value for snippet in source.snippets for value in (snippet.end, snippet.start) if value is not None]
    minutes = round(max(times) / 60, 1) if times else None
    return {
        "source_minutes": minutes,
        "leaf_units": len(leaves),
        "overview_ideas": len(knowledge.overview_ids),
        "visible_nodes": len(visible),
        "visible_leaf_units": sum(1 for unit in visible if not unit.child_ids),
        "visible_nodes_per_10_minutes": round(len(visible) / minutes * 10, 1) if minutes else None,
        "leaf_units_by_source_quarter": quarter_counts(leaves, positions),
        "visible_nodes_by_source_quarter": quarter_counts(visible, positions),
        "leaf_dig_deeper_depth": dict(sorted(histogram.items(), key=lambda pair: (not pair[0].isdigit(), int(pair[0]) if pair[0].isdigit() else 0))),
        "scope": "Visible means placed in a visual. Every unit remains reachable through saved detail and print.",
    }
