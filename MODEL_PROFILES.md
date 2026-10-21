# Adaptive model tasks

The pipeline uses model profiles to choose the largest allowed source section.
It keeps separate semantic extraction, synthesis, and source review. A full source
that fits the extraction budget is analyzed in one extraction task. Large sources
are covered by several tasks, followed by synthesis across the complete source.

Profiles are app policies, not provider capacity claims. Character counts are
planning estimates, not token counts. Output capacity is reserved with a
conservative heuristic: source characters cannot exceed 2.5 times output tokens.
The actual request includes skill instructions, schema and framing; these are
reserved separately. The app never truncates source content to fit.

## Defaults

| Provider and model | Source characters per task | Planned output tokens | Maximum extracted ideas |
|---|---:|---:|---:|
| Codex / CLI default | 40,000 | 16,384 | 40 |
| DeepSeek / deepseek-flash | 12,000 | 32,768 | 20 |
| Unknown model | 12,000 | 8,192 | 20 |

Codex's output value is a planning allowance; it does not set a CLI output flag.
DeepSeek's output value is sent as max_tokens. Actual task size may be smaller
because of request overhead and the output estimate. These new policies have not
yet been validated against real complete-video generations.

## Configure another model

Create `model-profiles.json` in the selected library folder. It contains no keys.
Each entry is keyed by the exact provider and model ID, separated by a colon.
Example: `{"deepseek:YOUR_MODEL_ID":{"input_characters":100000,"extraction_characters":50000,"output_tokens":32768,"maximum_units":48}}`

Only enter capacities supported by the selected model and connector. Save the
model ID in app Settings separately. Profiles are read when each job starts;
changing a profile creates a different checkpoint identity. Existing published
pages stay readable. This file configures capacity, not new provider endpoints.

Supported fields: `input_characters`, `extraction_characters`, `output_tokens`,
`maximum_units`, `minimum_split_characters`, `maximum_split_depth`, `adaptive`.
All numeric fields are bounded and validated. Set adaptive to false to disable
automatic section splitting while retaining normal field repair and validation.

## Recovery and cost

After truncated or invalid extraction output, the app divides only the failing
section, preserving one source passage of overlap. It saves the split decision
before running children. Retries reload that decision and completed child tasks,
instead of repeating the failed large request. Default split depth is four;
minimum child size is 2,500 characters. Further failures stop with diagnostics.

Invalid fields receive up to three repair attempts before splitting. A reported
output-length failure splits directly. Authentication, quota, billing, timeouts
and interrupted connections do not trigger this splitting. Existing worker
recovery rules still apply. The app never changes providers automatically.
Automatic repairs and smaller tasks can add calls and charges under the existing
paid-use approval. Providers may omit usage for failed requests; total billing
cannot be inferred from the generation record alone.

`generation.json` records the resolved profile, initial/completed window counts,
split reasons, depth, child sizes, and reported usage. It excludes raw failed
responses. Exact evidence and full coverage remain required. Source review and
synthesis remain separate stages; they do not yet adapt their task sizes in
response to output-length errors. Their existing input grouping still applies.

## Adding a connector later

Implement the existing `generate(prompt, schema, work_dir, progress)` contract and
return ProviderResult. Report truncated output as ProviderError with code
invalid_output and diagnostics.finish_reason set to length. Use the existing
transport/billing/quota error codes to avoid unintended automatic paid retries.
Attach a ModelProfile or register the exact provider/model identity in
model_profiles.py. Apply its output_tokens value through the provider's supported
output setting. A new connector also needs credential, Settings and approval
integration; this change does not add Gemini or GLM access.

ModelProfile can be attached directly to a provider for application integrations.
The same model identity plus profile and pipeline revision determines cache
compatibility. Future model changes cannot reuse incompatible extraction work.
