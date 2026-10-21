# Transcript analysis

Preliminary windows bound context; they are not semantic sections. Every supplied snippet must appear in at least one section. Overlap is context, not a new source. Assign source spans before compressing.

Extract coherent units with explanation, examples, conditions, and relevant relationships. Use meaningful verbs on relationships. Preserve changed positions and the speaker's claimed mechanism. Mark references to unseen diagrams, demonstrations, or code with `needs_visual` and a caveat.

Length is not complexity. A long conversation can hold few ideas; a short dense lecture can hold many. Extract each distinct substantive idea once; the number of units follows content, never window length. Give each section a `role` (substantive, anecdote, banter, sponsor, recap) and a `depth` (basic, intermediate, expert) judged by what it says, not how long it runs or how casually it is spoken. Greetings, small talk, sponsor reads, and repeated restatements get a section but no units.

Chapter synthesis receives one contiguous part of the source. Create one parent per distinct idea: merge restatements and closely related points, and keep distinct mechanisms, examples, numbers, and objections apart. Give the group a short chapter title. The reader's chapter notes show more or fewer children of each parent depending on the chapter's depth, so parent summaries need not repeat child detail.

During synthesis, group repeated and related ideas without throwing away underlying units. Parent `child_ids` must cover every supplied input unit. Use representative original quotations alongside extracted records; do not reason only from prose summaries. Select major overview concepts but retain branches with mechanisms, evidence, objections, and examples. Evidence needed for an exception should not disappear behind a stronger general claim.

When inputs exceed context, synthesize bounded groups recursively. Keep each stage artifact and stable references. Stop on insufficient context or invalid output rather than silently truncating. The final main conclusion must describe the supplied source, including disagreement or lack of a settled conclusion.
