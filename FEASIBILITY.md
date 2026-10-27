# Connector feasibility and limits

Checked locally on 2026-10-04. This report describes connector evidence. Whole-page learning quality and UI evaluation are reported separately.

## Caption retrieval

All eight supplied video IDs returned timestamped captions in the local feasibility probe. Records are saved in the local `.feasibility/` folder for repeatable development checks. This result is specific to this machine and network. It does not establish cloud retrieval reliability.

| Video ID | Selected caption language | Snippets | Last caption end |
|---|---|---:|---:|
| `0qqW3vxOC-g` | `en-US` | 252 | 09:25 |
| `lNWhbbAM59Y` | `en-US` | 196 | 24:35 |
| `-oladUKkhgo` | `vi` | 1,199 | 44:38 |
| `BfEfD0BRfDw` | `vi` | 792 | 26:51 |
| `jrnGl43pQl8` | `vi` | 470 | 13:43 |
| `d1X7LgYpRds` | `en` | 320 | 10:39 |
| `jLKQp4SgGr0` | `en` | 1,473 | 59:43 |
| `Blb6y9Um1r0` | `vi` | 1,411 | 44:37 |

An additional long source, `L_Guz73e6fw`, returned 3,206 English snippets with the last caption ending at 02:23:48. The retrieved title identifies the Sam Altman / Lex Fridman Podcast #367 discussion.

Caption end times describe the available text, not measured video duration. Caption display times can overlap. Automatic selection preserves an available caption track; it does not prove that the track is the original spoken language. A source-language setting selects a caption language explicitly. No machine-translation request is made to YouTube. No speakers are invented.

TXT, SRT, VTT, simple transcript JSON, and exported versioned transcript JSON are supported recovery inputs. Plain text keeps unknown timing. VTT voice tags preserve explicitly supplied speaker names. Invalid or non-finite times, repeated snippet IDs, unsupported file types, invalid UTF-8, and unsafe source URLs are rejected. A replacement JSON transcript naming another video is rejected when the job already identifies a video. Blocked retrieval is distinct from missing captions.

## Codex subscription connector

The earlier local real smoke used existing ChatGPT authentication and returned schema-shaped Vietnamese JSON in approximately seven seconds. The result is saved under `.feasibility/codex-smoke/`. This checks access and the output contract. It does not establish two-hour synthesis quality or a normal processing-time estimate.

The connector uses non-interactive `codex exec`, JSON event output, and a strict final JSON schema. It reuses saved authentication, forces ChatGPT authentication, removes API-key environment variables, and ignores user configuration and repository rules for this nested generation. Its job directory is isolated. Shell, patch, multi-agent, and web-search capabilities are disabled. Source text is supplied as untrusted data. The renderer consumes validated records rather than generated application code.

Each call has a bounded deadline. Standard input is written separately so an unread pipe cannot bypass the deadline. Cancellation or timeout stops the process; Windows also stops its descendants. Reader threads drain the event streams before classifying a completed request. Strict schema conversion preserves original field types and nullability. It does not turn optional Pydantic lists or strings into incompatible `null` values.

The connector explicitly requests `low` reasoning effort for balanced transcript work, as supported by the [official Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference). One configured model is used throughout a generation. A blank model field lets the CLI select its recommended model; the generation record labels this requested choice `CLI default`. The event stream used here does not report the resolved model, so it is not presented as a verified model ID. Higher reasoning effort is not enabled automatically.

[Official OpenAI non-interactive documentation](https://learn.chatgpt.com/docs/non-interactive-mode) documents saved CLI authentication, JSON events, and final output schemas. Hosted subscription arrangements and remaining account allowance have not been established here. No OpenAI API-key calls are made by this connector.

## DeepSeek connector

DeepSeek is available after an explicit paid-use setting or per-job approval. It does not activate when Codex fails. The default configured model is `deepseek-flash`; a model ID can be changed in Settings. The current Flash/V4 path requests low thinking effort with a 16,384-token output limit. Other configured model IDs keep the generic JSON request contract.

The connector sends JSON-mode chat requests and validates returned records through the same application pipeline. It detects truncated output, missing/invalid JSON, invalid credentials, account-balance errors, quota limits, and temporary service errors. It records usage when returned. Secrets stay in the operating-system credential store or explicit service environment variables. There is no plaintext key fallback.

No real DeepSeek request was sent. Access, actual model availability for the owner's account, billed usage, and learning quality remain unverified. The configured default follows the current official [JSON output guide](https://api-docs.deepseek.com/guides/json_mode/) and [thinking-mode guide](https://api-docs.deepseek.com/guides/thinking_mode/). Direct documentation opens were intermittently unavailable; indexed official pages provided the current model and parameter descriptions. Recheck these if the service rejects a model or parameter.

## Groq audio fallback

No video audio was downloaded and no audio was uploaded during connector verification. A real Groq key, free-account status, bilingual recognition quality, and Whisper model comparison remain unverified.

Audio processing requires an approved record containing the current job ID, source, Groq provider, and Whisper model. The free route also requires confirmation that the key belongs to a free account with no paid billing. A paid route requires explicit paid approval. An API request cannot impose free billing on an already paid Groq account; the app explains this before approval. The key is checked before any YouTube audio download.

The default is `whisper-large-v3-turbo`, with `whisper-large-v3` available. The [Groq transcription guide](https://console.groq.com/docs/speech-to-text) lists multilingual segment timestamps, 25 MB free uploads, and 16 kHz mono preparation. The implementation uses ten-minute PCM WAV sections with three-second overlap on both sides where available, checks every upload against a 24,000,000-byte safety limit, and restores original offsets. It keeps silence in the time axis. The maximum source duration is six hours to bound local conversion storage.

Only trusted local media formats and local file/pipe protocols are accepted by FFprobe and FFmpeg. Uploaded playlists cannot request external URLs through these commands. A locally generated WAV was actually converted and checked for one channel at 16 kHz. YouTube audio still depends on yt-dlp, its JavaScript challenge dependencies, current video access, and the selected audio track. Original spoken-track selection on videos with multiple dubs is not proven.

Each validated section is saved before the next upload. A quota response preserves completed sections and reports the provider's wait time. Retry starts at the unfinished section. Saved audio cannot be reused with a different source, audio hash, language, or model. Overlap deduplication only compares adjacent chunk content with overlapping times; later repeated statements remain. Partial boundary trimming and low-confidence segments produce review warnings.

The [published Groq free limits](https://console.groq.com/docs/rate-limits) currently show 7,200 audio seconds per hour and 28,800 per day for both Whisper models. Actual account limits can differ. Three-hour recordings may wait between sections. The app obeys service quota responses and never changes billing plans automatically.

Successful managed audio is deleted by default. User input originals are preserved; the application also removes its own imported copy when the source checkpoint is saved. Failed managed audio becomes eligible for cleanup after 24 hours on worker activity; deletion does not run while the app is closed. A delete action is provided in the processing UI. Cloud HTTP requests have bounded network timeouts. A request already in flight can still use quota or paid usage after cancellation. No following section is sent after cancellation is observed. An uncertain cloud timeout or interrupted connection requires manual retry. A connection timeout before a request is sent can use bounded automatic retry.

## Local connector checks

`app_tests/test_connectors.py` contains 65 passing targeted checks. They cover URL validation, captions versus blocked retrieval, recovery formats and source identity, timestamps, strict schemas, key redaction, paid consent, Codex structured events, explicit low reasoning effort and blocked-pipe timeout, quota classification, uncertain cloud request retry boundaries, audio approval, offsets, repeated text, malformed STT output, checkpoint recovery, cancellation, and local FFmpeg conversion.

Run them with `.venv\Scripts\python.exe -m pytest app_tests/test_connectors.py -q` from the repository root. These checks use fake API responses; they do not send remote AI or speech requests. The actual local environment uses Python 3.14.4, FastAPI 0.142.2, Pydantic 2.13.5, and yt-dlp 2026.8.19. Python 3.12 remains the conservative suggested installation version, but the tested local environment is 3.14.

## Release limits

Caption retrieval and real Codex structured access passed locally. DeepSeek and Groq live quality/access comparisons still require owner-configured keys and the stated usage approval. Full learning-page evaluation must check source claims, relationships, caveats, technical terms, and source links against original text. Passing connector checks does not prove educational accuracy. Private hosting, owner login, cross-device sync, live AI exploration, visual video analysis, and other deferred features are outside V1.
