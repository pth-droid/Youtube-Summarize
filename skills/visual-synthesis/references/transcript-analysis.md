# Transcript analysis

Preliminary windows bound context; they are not semantic sections. Every supplied snippet must appear in at least one section. Overlap is context, not a new source. Assign source spans before compressing.

Extract coherent units with explanation, examples, conditions, and relevant relationships. Use meaningful verbs on relationships. Preserve changed positions and the speaker's claimed mechanism. Mark references to unseen diagrams, demonstrations, or code with `needs_visual` and a caveat.

During synthesis, group repeated and related ideas without throwing away underlying units. Parent `child_ids` must cover every supplied input unit. Use representative original quotations alongside extracted records; do not reason only from prose summaries. Select major overview concepts but retain branches with mechanisms, evidence, objections, and examples. Evidence needed for an exception should not disappear behind a stronger general claim.

When inputs exceed context, synthesize bounded groups recursively. Keep each stage artifact and stable references. Stop on insufficient context or invalid output rather than silently truncating. The final main conclusion must describe the supplied source, including disagreement or lack of a settled conclusion.
