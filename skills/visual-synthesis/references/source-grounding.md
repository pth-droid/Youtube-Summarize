# Source grounding

`source`: the cited original passage supports the claim. Preserve the speaker's attribution and qualifiers. `inference`: reasoning based on cited passages but not directly asserted there; explain the reasoning and limits. `background`: added teaching context, with no borrowed transcript citation. `uncertain`: insufficient, contradictory, or ambiguous support; show the limitation.

Evidence has original `snippet_ids` and a verbatim `quote`. Each evidence entry cites one contiguous span, with snippet IDs in original order. Use separate evidence entries for disconnected passages. Quote only what the cited span actually contains. Do not invent a timestamp, page, speaker, number, source, or technical term. Source snippets can overlap; their caption display duration is not exact speech duration.

Relationships have their own evidence and status. Evidence for two nodes does not automatically support an arrow between them. A `causes` relationship needs an explicit causal statement or a clearly labelled inference with its reasoning basis. Temporal order is not causation. Preserve objections and caveats with the associated claims.

A semantic review checks names, numbers, negations, caveats, missing prerequisites, and unsupported arrows against original passages. Report issue IDs and concrete reasons. Do not use outside knowledge to silently correct the source or declare the speaker's claim verified.
