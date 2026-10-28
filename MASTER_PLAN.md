# Distill — Master Plan

Status: Planning complete; implementation is not authorized by this document.

Date: 2026-10-04

## 1. Product outcome

Turn a long YouTube video into a source-grounded, interactive mental model.

The page should help the reader understand the main question, major ideas, mechanisms, dependencies, disagreements, and supporting evidence. The reader can move from an overview to details and then to the exact source passage.

The product is optimized for understanding and exploration. Quizzes are not part of the required workflow.

### First complete user journey

1. Paste one YouTube URL.
2. Optionally choose a learning goal, knowledge level, language, or AI provider.
3. Retrieve captions and preserve their timestamps.
4. If captions cannot be obtained, explain the failure and ask before audio processing.
5. Analyze the complete available transcript in stages.
6. Build a knowledge model and select suitable visual forms.
7. Save a learning page in the library.
8. Explore the page or export it as one standalone HTML file.

## 2. Agreed scope and defaults

| Area | Decision |
|---|---|
| Initial deployment | Local app, opened in a browser |
| Future deployment | Private online access for the owner across devices |
| Initial processing | Local worker; computer must remain on |
| Future processing | Optional hosted worker that can run while the computer is off |
| Primary AI | Codex CLI using the owner's existing subscription |
| Secondary AI | DeepSeek API with usage charges |
| Other AI providers | Keep a connector design for GLM and Gemini; defer implementation until needed |
| Audio fallback | Groq free cloud transcription, after explicit approval |
| Paid fallback | Never switch to paid processing silently |
| Output language | Vietnamese, preserving original technical terms |
| Language option | English, especially for English source videos |
| Quality target | Balance source accuracy, useful detail, processing time, and cost |
| Learning preference | Saved knowledge level and an optional goal per video |
| Exploration | Saved expandable detail in V1; live AI generation later |
| Source scope | Transcript first; mark references that depend on unseen visuals |
| Added explanations | Allowed, clearly labelled as background or inference |
| Storage | SQLite index plus ordinary files |
| Export | One self-contained interactive HTML file |

The library is the durable working record. Exported HTML is a portable snapshot of a chosen page version.

## 3. Success criteria

A useful page lets the reader quickly answer:

- What is the source about, and what is its main conclusion?
- Which ideas matter most?
- What causes what, and what depends on what?
- Where do claims, evidence, and opinions differ?
- How does the process or mechanism work?
- Where was each important point discussed?

The first screen should show one clear orientation statement and roughly 5–8 major ideas. Fewer ideas are acceptable when the material supports fewer. Do not add weak nodes to meet a count.

Use 2–3 complementary visualizations when useful. Do not force the same three diagrams onto every video.

Proposed acceptance exercise: after five minutes with a page, the owner should be able to explain the big picture, identify three useful relationships, and locate supporting source passages. This is a product evaluation exercise, not a quiz feature.

## 4. Recommended technology

| Component | Choice | Purpose |
|---|---|---|
| Application runtime | Python 3.12 initially | Shared runtime for retrieval, processing, and the local service |
| Local web service | FastAPI with Uvicorn | Serves the interface and provides job/library endpoints |
| Application interface | HTML templates, CSS, and small JavaScript modules | Keeps V1 simple while supporting library and progress screens |
| Data validation | Pydantic and versioned JSON schemas | Checks knowledge, presentation, and provider outputs |
| Library index | SQLite through Python's built-in support | Stores records, settings, jobs, and versions without a database server |
| Artifact storage | Local filesystem | Stores source transcripts, models, and exported pages |
| Processing | One separate Python worker process | Runs long jobs without blocking the interface |
| Caption retrieval | Existing `youtube_transcript_api` package | Reuses the repository's caption and timestamp handling |
| Audio retrieval | yt-dlp with its required JavaScript runtime | Retrieves the selected original audio track after approval |
| Audio preparation | FFmpeg | Prepares and splits audio for transcription |
| Speech recognition | Groq Whisper connector | Produces text with segment timestamps |
| Primary AI connector | Codex CLI subprocess | Runs the skill with subscription authentication |
| Secondary AI connector | DeepSeek API client | Runs equivalent analysis with explicit API configuration |
| Export rendering | HTML, CSS, inline SVG, JavaScript | Produces an offline reading and exploration experience |
| Browser verification | Headless Playwright Test | Checks page behavior, source links, and responsive layouts |

No database server, graph database, vector database, Redis, or multi-agent framework is needed for V1.

Use the current transcript package as a dependency boundary. Add the application beside it; avoid mixing learning features into its upstream library modules. Confirm Python and dependency compatibility when implementation begins.

## 5. Architecture and responsibilities

| Layer | Owns |
|---|---|
| Browser interface | Input, preferences, approvals, progress, library, and reading |
| Application service | Request validation, job creation, artifact access, and settings |
| Job store | Pending work, active leases, checkpoints, retries, and approval state |
| Worker | Retrieval, provider calls, validation, rendering, and recovery |
| Agent Skill | Semantic analysis, source-grounding rules, teaching depth, and visual selection |
| Provider connectors | Authentication, request format, context limits, output handling, and usage reporting |
| Renderer | Layout and interaction for the agent's validated presentation choices |
| Storage interface | Reads and writes independent of local paths or future cloud storage |

The agent determines meaning. Scripts handle predictable operations such as parsing, validation, layout, timestamp conversion, and file packaging.

The skill is an instruction package, not a running service. The worker provides its execution environment. The Codex connector invokes it through the CLI; the API connector supplies the relevant instructions and schemas explicitly. Both produce the same artifact contracts.

### Processing flow

YouTube URL → durable job → captions or approved audio transcription → timestamped source → semantic sections → knowledge model → presentation plan → validated HTML → library.

Closing the browser does not cancel a job. Closing the worker or shutting down the computer pauses processing; the next launch resumes from the last durable checkpoint.

## 6. Source ingestion

### YouTube input

- Accept standard watch URLs, short URLs, and supported mobile/shorts URL forms.
- Extract and validate a video ID before calling the transcript library.
- Use the selected source language; prefer suitable manual captions over generated captions.
- Preserve language, caption origin, retrieval date, and available video metadata.
- Detect existing imports and offer the saved result or an explicit new generation.
- Do not translate or flatten the source before saving it.

The existing snippet structure includes text, start time, and caption display duration. Display duration is not exact speech duration, and captions can overlap. Preserve this distinction.

Speaker identity is optional. The existing package does not supply structured speaker names. Do not invent speakers from turn order or confuse an inferred identity with a verified identity.

### Retrieval failures

Distinguish missing captions from temporary network errors, blocked requests, language mismatch, and inaccessible videos. Apply bounded retries to temporary failures. Offer available caption languages when appropriate.

A blocked caption request does not prove that captions are absent, and audio download may also be blocked. If retrieval fails, offer transcript/subtitle import or audio-file import.

Support TXT, SRT, VTT, and transcript JSON as recovery inputs in V1. Plain text has no verified timestamps; show that limitation instead of generating false links.

## 7. Audio fallback and approval

Before downloading or uploading audio, show:

- Why captions could not be obtained.
- Video duration, if known.
- The selected transcription provider and model.
- That audio will be sent to Groq.
- Available quota information, or a clear statement that remaining quota is unknown.
- Whether processing is free-tier only or paid processing has been selected.
- Actions to continue, import a transcript, or cancel.

Approval is saved for that job, source, and provider choice. Resuming the same approved work does not require repeated confirmation. Switching to a paid route requires new approval unless an applicable explicit spending preference already covers it.

### Audio processing design

1. Download audio only, selecting the original spoken track where available.
2. Use FFmpeg to produce an appropriate speech format.
3. Split into bounded sections that meet current upload limits, preferably at speech boundaries.
4. Keep a small overlap and record each section's original time offset.
5. Request segment timestamps and save each successful response.
6. Merge sections, remove overlap duplicates, and restore absolute video times.
7. Flag gaps, repeated text, or suspicious transcription spans.
8. Keep the original-language transcript for evidence.

Silence handling must preserve original timing. Do not concatenate speech and lose its position in the source video.

Start by evaluating Groq `whisper-large-v3` and `whisper-large-v3-turbo` on representative audio. The final default depends on accuracy and waiting time. Both currently have published free-tier allowances; those limits are not a permanent service guarantee.

On quota exhaustion, checkpoint and wait according to service retry information. Do not evade limits or silently enable billing. Failed sections can be retried independently.

Delete temporary audio after successful transcript validation by default. Retain failed-job audio for a documented short recovery period, with a delete action and storage limit. Allow the owner to opt into retaining source audio.

## 8. Agent Skill and semantic pipeline

### Proposed skill layout

- `skills/visual-synthesis/SKILL.md`
- `skills/visual-synthesis/references/transcript-analysis.md`
- `skills/visual-synthesis/references/source-grounding.md`
- `skills/visual-synthesis/references/visual-selection.md`
- `skills/visual-synthesis/references/interaction-patterns.md`
- `skills/visual-synthesis/references/learning-depth.md`
- `skills/visual-synthesis/schemas/`
- `skills/visual-synthesis/templates/`
- `skills/visual-synthesis/scripts/` for deterministic helpers where useful.

### Stage A: Prepare and segment

Assign stable IDs to source snippets. Detect topic boundaries and preserve the source order. Use bounded windows with overlap when the complete input exceeds the selected provider's context budget. Never silently truncate a long source.

Semantic segmentation is the agent's task. Preliminary splitting by time or size is a processing aid, not the final topic structure.

### Stage B: Extract knowledge

For each section, capture questions, claims, concepts, mechanisms, examples, evidence, numbers, caveats, prerequisites, and disagreements. Retain source span references before any compression.

### Stage C: Synthesize across sections

Merge repeated concepts and connect related ideas across the video. Preserve contradictions and changes in position. Select the major ideas for the overview while keeping useful detail accessible.

Use extracted records plus relevant original passages during synthesis. Do not build the final result only from increasingly compressed prose summaries.

### Stage D: Ground and teach

Each important claim and relationship needs supporting source spans or an explicit status such as inference, added background, or unsupported/uncertain.

Distinguish “the speaker claims” from verified fact. V1 does not perform routine external fact checking. Added background must not inherit a source citation that does not support it.

Adapt explanations to the saved knowledge level and optional learning goal. Preserve original technical terms in Vietnamese output, with a short definition where useful.

### Stage E: Select visual grammar

| Structure in the material | Candidate visual |
|---|---|
| Concepts and their relationships | Concept map |
| Supported causal explanation | Causal graph |
| Ordered mechanism or procedure | Process diagram or stepper |
| Claim, evidence, and objection | Argument map |
| Change over time | Timeline |
| Levels and prerequisites | Hierarchy or dependency diagram |
| Competing choices and trade-offs | Comparison view |
| Primarily hierarchical material | Markmap, if it materially improves the result |

Draw causal arrows only when the source supports causation or the page labels the relationship as an inference. Label connections with meaningful verbs.

### Stage F: Validate and render

Validate schemas, IDs, references, time ranges, and presentation mappings. Repair invalid output with bounded attempts. Structural validation does not establish factual accuracy; perform a separate grounding review against the cited passages.

The renderer implements a small set of adaptable components. The agent chooses components, groupings, emphasis, and relationships. V1 should not execute arbitrary model-generated application code.

## 9. Artifact contracts and storage

| Artifact | Required information |
|---|---|
| Source | Video ID, URL, metadata, language, origin, retrieval date, and content hash |
| Transcript | Stable snippet IDs, original text, start/end times when available, optional speaker, and timing basis |
| Knowledge model | Main question/conclusion, concepts, claims, relationships, examples, caveats, source spans, and grounding status |
| Presentation plan | Visual types, stable knowledge references, overview selection, disclosure layers, and reading order |
| Generation record | Provider/model, skill/schema versions, preferences, input hashes, duration, usage, and known limitations |
| Learning page | Self-contained HTML snapshot with embedded data and assets |

Use explicit schema versions. Generate a new page version when language, goal, model, or analysis changes. Preserve previous successful versions until the user deletes them.

Store short records and indexes in SQLite: videos, source versions, generations, jobs, approval state, preferences, and schema migrations. Keep large artifacts in per-source/per-generation folders.

SQLite needs no separate server. Use short transactions and a separate connection per process. Claim jobs atomically and use leases/heartbeats to recover interrupted work. Start with one worker and one active generation.

Write artifact files atomically, then publish the completed generation in the database. Never present partial HTML as a finished page. Include a backup/export bundle containing the database and referenced files.

Secrets belong in an operating-system credential store or protected service environment. They must not appear in SQLite records, exports, logs, or prompts.

## 10. Job lifecycle and recovery

Suggested states: queued, retrieving, awaiting approval, transcribing, analyzing, selecting visuals, validating, rendering, complete, waiting for quota, failed, and cancelled.

Persist stage checkpoints and section results. Display the current stage and completed units rather than a fabricated completion percentage or unmeasured time estimate.

Use bounded retries with backoff for temporary errors. Stop on invalid credentials or exhausted budgets. Record clear user-facing failure reasons without exposing credentials or raw internal logs.

Cache by source hash, language, provider/model, skill/schema version, and relevant preferences. Reuse transcripts across generations. Reuse knowledge for presentation-only changes. Do not reuse an analysis when a new learning goal materially changes its scope.

## 11. Interface and learning page

### Application screens

1. **Library:** saved pages, search, filters, status, and import action.
2. **New learning page:** URL field; saved language/level; optional goal; provider selection.
3. **Processing:** stages, quota waits, approval requests, retry, and cancellation.
4. **Reader:** visual overview, detail panels, source evidence, and export.
5. **Settings:** providers, credentials, preferences, storage, and explicit paid-use controls.

### Reader behavior

- Show the big picture before detailed material.
- Support expand, collapse, focus, relationships, evidence, and source navigation.
- Provide a clear return-to-overview action.
- Reveal saved mechanisms, examples, and caveats under “Dig deeper.”
- Keep critical caveats visible with the claims they qualify.
- Show original supporting text beside translated explanations.
- Use timestamp links to open the original YouTube video.
- Identify content that depends on unseen demonstrations or slides.
- Provide touch and keyboard access; do not rely on hover or color alone.
- Use narrow-screen detail sheets or sections so diagrams remain readable on phones.

V1 “Dig deeper” reveals already generated material. A future action to generate a new explanation must be distinct and indicate that AI processing is required.

### Export contract

Embed CSS, JavaScript, required data, and essential visual assets. Avoid runtime CDN dependencies. Any optional visualization library must be bundled appropriately with required license notices.

The exported page works offline for reading and saved interactions. YouTube playback and external source links require internet access. Export does not include API credentials, live generation, or a promise to sync later reading state.

## 12. Provider and model policy

- Use one balanced model per generation initially.
- Make model IDs configurable and validate provider capabilities.
- Track context budget, structured-output support, timeouts, and usage reporting per connector.
- Keep the same knowledge schema across Codex and DeepSeek.
- Use available CLI progress events and structured final output without depending on human-formatted terminal text.
- Limit Codex to the current job's files and required capabilities. Source text is data, not permission to execute instructions.
- Preserve work when a provider reaches its limit.
- Offer a manual provider switch; do not assume partial outputs from different models are interchangeable.
- Show measured usage where provided; label cost estimates and unavailable subscription balance information.

Select models using source accuracy, relationships, explanation quality, output validity, latency, and cost. Do not choose a frontier model solely because it is newer or more capable on unrelated tasks.

## 13. Security and deployment boundaries

Local service binds to loopback by default. Validate request origins and avoid treating knowledge artifacts as executable input. Escape transcript content, validate source URLs, and restrict filesystem access to managed data locations.

For the later private online version, add owner authentication, HTTPS, protected artifact access, and service-side secret storage before exposure. Public user accounts, billing, and sharing are outside the agreed scope.

Keep generated HTML isolated from the application's authenticated origin when it can contain executable content. Prefer controlled renderer output throughout V1.

## 14. Path to private online use

### Phase 1: Fully local

App, SQLite, files, and worker run on the owner's computer. Codex uses its existing local authentication. Groq is used only after approval.

### Phase 2: Private online library

Make saved learning pages available across devices behind owner authentication. Define an explicit publish/sync mechanism and authoritative storage location. Do not place a live SQLite database in a generic file-sync folder and assume concurrent edits are safe.

Generation can remain local. An online library does not require a hosted processing worker.

### Phase 3: Optional hosted processing

Evaluate Cloud Run Jobs as an on-demand worker candidate. Use durable external storage for jobs and artifacts; a job container's local files are temporary. Reassess the database choice for the selected hosting layout. A private single-server deployment with durable disk may still use SQLite.

DeepSeek API is the planned straightforward hosted AI option. Hosted use of the owner's Codex subscription remains unverified and must be checked against current supported authentication and usage arrangements before adoption.

Cloud hosting has a separate cost from transcription and LLM usage. Free allowances are not an unconditional zero-cost guarantee. Cloud YouTube retrieval may be blocked; test this separately before promising fully unattended hosted ingestion.

## 15. Implementation sequence and exit checks

| Stage | Deliverable | Exit check |
|---|---|---|
| 0. Feasibility | Verify Codex output contract, caption retrieval, and Groq access | One real source can be retrieved and analyzed; limitations recorded |
| 1. Learning quality prototype | Skill, knowledge schema, grounding rules, and first renderer | One long discussion produces a useful cited page with saved detail |
| 2. Local application | Library, SQLite, settings, durable queue, worker, and progress | Paste URL → saved page works; browser closure does not cancel work |
| 3. Approved audio fallback | Audio approval, download, splitting, transcription, and resume | Missing-caption path preserves timestamps and waits safely on quota |
| 4. Provider flexibility | DeepSeek connector and manual switching | Both providers satisfy the same artifact contracts |
| 5. Reader and export | Focus/expand/evidence/source behavior and offline export | Desktop and mobile checks pass; exported page has no required network assets |
| 6. V1 evaluation | Full supplied example set and failure scenarios | Quality issues resolved or explicitly documented before release |
| Later | Private online access, hosted worker, live AI | Separate deployment and product decisions after V1 evidence |

Stage 0 may use short audio samples to measure fallback quality before building the complete audio feature. Any download/upload follows the user's approval rule.

No code changes, dependency installations, paid requests, or transcription runs are performed as part of writing this plan.

## 16. Evaluation sources

The owner supplied these eight videos. Their full contents and caption availability have not yet been verified. Earlier browser retrieval was mostly throttled.

| Category supplied by owner | Video |
|---|---|
| Podcast/discussion | https://www.youtube.com/watch?v=0qqW3vxOC-g |
| Podcast/discussion | https://www.youtube.com/watch?v=lNWhbbAM59Y |
| Podcast/discussion | https://www.youtube.com/watch?v=-oladUKkhgo |
| Podcast/discussion | https://www.youtube.com/watch?v=BfEfD0BRfDw |
| Podcast/discussion | https://www.youtube.com/watch?v=jrnGl43pQl8 |
| Review | https://www.youtube.com/watch?v=d1X7LgYpRds |
| Tutorial | https://www.youtube.com/watch?v=jLKQp4SgGr0 |
| Tutorial | https://www.youtube.com/watch?v=Blb6y9Um1r0 |

Start with one discussion, the review, and one tutorial. Expand to all eight. Ensure the evaluation also includes a verified 1–3 hour recording if the supplied set does not contain one.

### Checks during implementation

- Compare important nodes and relationship labels with their original passages.
- Check evidence from the beginning, middle, and end of long videos.
- Check names, numbers, negations, technical terms, disagreements, and caveats.
- Confirm no source section was silently lost during input splitting.
- Evaluate Vietnamese clarity and preservation of English terminology.
- Evaluate timestamp accuracy around audio-section boundaries.
- Compare selected model outputs on identical source samples.
- Record processing time, provider usage, retries, and peak local resource use.
- Exercise missing captions, blocked retrieval, quota exhaustion, invalid credentials, cancellation, and worker restart.
- Use targeted unit/integration tests for job recovery, offsets, deduplication, schemas, and storage consistency.
- Use headless Playwright Test for reader interactions, source links, responsive layout, console errors, and offline export.
- Inspect real pages visually; schema and browser checks alone cannot prove teaching quality.

Numerical accuracy and latency targets should be set after the first measured baseline. Do not promise a fixed generation time before those measurements.

## 17. Deferred features

- Live AI chat, new branch generation, and natural-language page rearrangement.
- Cross-video concept merging and long-term learning recommendations.
- Video frame analysis, OCR, and screenshot-based tutorial reconstruction.
- Automatic speaker diarization and identity recognition.
- Routine external research and fact checking.
- General article, paper, and document ingestion beyond recovery transcript files.
- Batch playlists, public accounts, paid subscriptions, and collaborative editing.
- Local speech recognition as an additional fallback.

Keep extension boundaries for these features, but do not build their infrastructure in advance.

## 18. Risks and unresolved measurements

| Risk or unknown | Planned response |
|---|---|
| YouTube retrieval changes or blocks requests | Separate retrieval connector, clear failure types, imports, and measured cloud feasibility |
| Incorrect relationships or unsupported causal arrows | Evidence on relationships, explicit inference labels, and grounding review |
| Transcript errors distort the explanation | Preserve raw text, flag uncertain spans, check names/numbers, and link to source |
| Long inputs lose detail | Source coverage tracking, section extraction, and synthesis using original passages |
| Codex account limits or CLI changes | Bounded connector contract, saved checkpoints, and manual DeepSeek option |
| Free Groq quota is unavailable or changes | Read service responses, wait safely, and avoid automatic paid fallback |
| Diagrams become crowded | Small overview, focused subviews, and progressive disclosure |
| Template system becomes too restrictive | Compose visual components by semantic purpose and record unsupported structures |
| Files and database become inconsistent | Atomic writes, completion records, backups, and restart checks |
| Unmeasured performance | Benchmark representative sources before setting service targets |

The next action after approval to implement is Stage 0. No further product choice is required to begin that feasibility work.

## 19. Research and design references

Documentation was reviewed during planning. Recheck provider limits, prices, and authentication support during implementation.

- [Existing transcript library](https://github.com/jdepoix/youtube-transcript-api): caption retrieval and known blocking limitations; also inspect the local repository.
- [Visual Explainer](https://github.com/nicobailon/visual-explainer/blob/main/plugins/visual-explainer/SKILL.md): visual-first explanations, mechanisms, and progressive disclosure. Adapt its output rules to require fully embedded offline assets.
- [Mindmap Skills](https://github.com/galiacheng/mindmap-skills): hierarchical views when appropriate.
- [Matt Pocock teach](https://github.com/mattpocock/skills/blob/main/skills/productivity/teach/SKILL.md): persistent mission, sources, and reference material. Mandatory quizzes and practice workflows are excluded.
- [Matt Pocock research](https://github.com/mattpocock/skills/blob/main/skills/engineering/research/SKILL.md): possible later research step.
- Local `visual-knowledge-publisher` skill: separate the knowledge model from presentation and preserve source fidelity.
- [FastAPI](https://fastapi.tiangolo.com/) and [Pydantic](https://docs.pydantic.dev/latest/): application service and output validation.
- [Codex automation](https://developers.openai.com/codex/noninteractive) and [authentication](https://developers.openai.com/codex/auth): CLI integration and access modes.
- [DeepSeek documentation](https://api-docs.deepseek.com/): API integration; exact model configuration to be verified.
- [Groq transcription](https://console.groq.com/docs/speech-to-text) and [rate limits](https://console.groq.com/docs/rate-limits): timestamps, file handling, and free quotas.
- [yt-dlp JavaScript requirements](https://github.com/yt-dlp/yt-dlp/wiki/ejs): audio retrieval dependencies.
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper): possible later local transcription.
- [Cloud Run pricing](https://cloud.google.com/run/pricing): future hosted job evaluation.

Check licenses and preserve required attribution before copying upstream code, templates, or skill content. References are design inputs, not dependencies that must all be installed.
