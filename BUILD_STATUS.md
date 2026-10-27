# Distill build status

Updated 2026-10-06. This is the local V1 implementation. The master plan's later online and live-AI stages remain deferred.

## Delivered

- Local browser app with Learn something new, Library, Processing, Reader, and Settings views.
- Learn something new is the default home page. Paste a YouTube link and select Create learning page or press Enter. Saved language, level, and provider are shown below the link. Page options are collapsed, with separate access to saved defaults and transcript/audio imports. Settings must load before creation is enabled. API approval stays visible when required.
- Provider access is a hub for user-named connections. Add an endpoint, model ID, API format, and optional saved key. Several models can share a provider. Edit, select a default, remove a saved key, or remove a connection. Existing connections remain usable. Saved pages retain their connection name. The menu calls the home page Start learning.
- Timestamp-preserving YouTube caption retrieval; TXT, SRT, VTT, and JSON transcript imports; local audio imports with cloud approval.
- Separate durable worker; one active job across worker processes; lease recovery, cancellation, checkpoints, compatible retry, and quota waits.
- Codex subscription connector as the default; explicit paid DeepSeek connector; Groq audio fallback with per-source approval and free-account confirmation.
- Versioned source, semantic, presentation, and generation records. Agent reasoning selects concepts, relationships, supporting evidence, and suitable visuals before controlled HTML rendering.
- Seven visual forms: concept map, causal graph, process, argument map, hierarchy, comparison, and source timeline.
- Vietnamese explanations with original technical terms, English option, knowledge level, learning goal, saved child ideas, evidence, source passages, and timestamp links.
- One self-contained HTML export that works offline. Source video links require internet. Printable reference content is also supplied.
- SQLite with normal artifact files; managed deletion; library ZIP backup; restore instructions; operating-system credential storage.
- Settings control to change the library folder, with full copy, database integrity check, preserved original backup, separate remembered startup location, and worker continuation. Active, queued, or quota-waiting processing blocks the change.
- Double-click Windows launcher and PowerShell setup/start scripts. Guide: [APP_GUIDE.md](APP_GUIDE.md).

## Verification evidence

The library folder update passed **9 dedicated Python checks** for preserved pages, sources, preferences, imported audio paths, checkpoint paths, restart selection, busy-job blocking, destination validation, old-writer rejection, and failed-selection recovery. A headless Playwright Test check changed the folder through Settings, reopened the saved export, reloaded the page, and processed a new import through the worker in the new folder. The earlier combined core regression run passed **29 checks** before the final missing-drive check was added. Production data was not moved during these checks.

The latest combined Python run passed **130 checks**: connector behavior, long-input request bounds and source coverage, evidence validation, model repair limits, semantic checkpoints, consent, paid retry safety, worker leases, cancellation, import recovery, export isolation, audio cleanup, backup/restore, usage reporting, and worker lifecycle. Seventeen provider-hub checks cover custom connection creation, independent models and keys, default submission, approval, updates, deletion, busy-job protection, retry compatibility, validation, credential failure, both API formats, and saved page names after connection removal. Tests ran with `.venv\Scripts\python.exe -m pytest app_tests tests_app -q`.

The latest full **headless Playwright Test run passed 27 checks**. Six provider-hub checks cover an empty hub, arbitrary provider/model/endpoint creation, keys in an isolated credential fixture, custom defaults used in a submitted job, multiple models, edits and reload, default removal, invalid endpoints, escaped names, and mobile API format selection. Eight home-page checks cover default navigation, saved preferences in a real submitted job, Enter to start, page overrides and reset, delayed or unavailable settings, API approval, mobile imports, and explicit links after reload. Six workspace checks cover library relocation with worker continuation, saved reader interactions, evidence/source navigation, offline export, file import through the UI, caption failure consent and cancellation, diagnostic polling, settings persistence, backup, and mobile layout. Seven additional checks exercise every visual grammar on desktop and mobile, with no internet requests, JavaScript errors, or document-width overflow. Process order, hierarchy, argument objections, comparison fields, timeline source links, and evidence navigation are asserted. The saved real Codex excerpt is included in mobile reader inspection when available. The home-page and provider-hub updates used isolated fixtures; they did not make live AI requests.

Browser verification uses Chromium in headless mode. It does not operate the user's open browser. Screenshots are stored locally in `.feasibility/screenshots/`; the temporary libraries are removed after the test server stops. The app's actual library contains no authored test fixture.

Manual screenshot inspection confirmed legible desktop and mobile cards, intact Vietnamese text, reachable mobile navigation, and readable evidence panels. The 2026-10-06 home-page screenshots show the link and start button in view on desktop and mobile, with page options collapsed. The initial mobile navigation clipping and settings refresh race were corrected. One upstream Starlette/TestClient dependency deprecation warning remains in the Python test output; it did not affect these results.

Local caption retrieval passed for all eight user-supplied video links, plus a 2:23:48-caption-span podcast. See [FEASIBILITY.md](FEASIBILITY.md) for exact selected tracks, source counts, connector details, and sources. This is local network evidence; cloud YouTube access remains unproven.

A real Codex subscription run generated a Vietnamese learning page from a **24-caption excerpt**, with five overview ideas and two visual forms. The stored title marks it as an excerpt. This proves the live source-to-semantic-to-HTML connection for that excerpt. It does not prove quality for an entire long video. Checkpoint reuse means its final `generation.json` duration and token records describe the latest processing invocation, not the full initial run. The UI labels recorded usage scope and unknown subscription allowance.

The full-source semantic evaluation is being completed separately. This document must be updated with its actual result before claiming that a complete two-hour transcript has produced a validated final learning page.

## Local launch

The 2026-10-05 folder-control update is live at the same local URL. A scoped app restart preserved the in-progress source and first extraction checkpoint; the worker reclaimed the same job after its lease expired. A headless browser confirmed the populated folder field and visible **Change library folder** control. The production library location was not changed.

The app is available at **http://127.0.0.1:8765**. The health endpoint reported `status: ok` and `worker: running`. Its storage is `C:\Users\phant\AppData\Local\VisualLearning` on this machine. The current final-development launch is hidden and opens no browser automatically. The normal double-click launcher keeps a visible window that the owner can close.

To start again, use **Start Distill.cmd**. Setup and restore details are in the guide. The web service listens only on loopback. The worker can continue while the browser is closed, and managed work survives a worker restart. Windows shutdown stops the worker's descendants, including nested CLI or media processes.

## Remaining limits

- DeepSeek and Groq live account access, billing, bilingual audio quality, and Whisper model comparison are unverified. No paid request or real video-audio upload was made during verification. They need owner-configured keys and the stated approval.
- A free Groq key's billing plan cannot be enforced by an API parameter. Account confirmation is required. Quota can pause long audio jobs.
- Source grounding links the generated claims to supplied text. It does not prove that a speaker is correct or that every subtle point has been retained. The semantic review can mark uncertain conclusions and relationships. External fact checking is deferred.
- The supplied examples' caption spans are below one hour. The additional podcast supplies a real source above two hours; full-page evaluation must report its outcome separately.
- Processing time and token use depend on source length, selected model, provider allowance, retries, and saved checkpoints. No general latency or cost promise is made.
- YouTube captions and downloads can be blocked. Source-language selection handles caption tracks; original spoken audio track selection on dubbed videos is not proven. Imported transcript/audio recovery remains available.
- Backup waits for active or queued jobs to stop, then holds a writer gate while copying. A large audio backup can take time. Worker database contention waits instead of exiting. Keep database and artifact files together for restore.
- Audio cleanup runs while the worker is active. Failed or cancelled audio is eligible after 24 hours, unless retention is enabled. A source copy already removed after successful transcription cannot be retranscribed; import a new audio job instead.
- Hosted worker, private owner login, HTTPS deployment, cross-device sync, GLM/Gemini connectors, live AI exploration, general document input, video-frame analysis, and quizzes are outside this local V1.

## Main implementation files

`distill/app.py` serves local routes. `storage.py` manages metadata and artifacts. `worker.py` runs saved jobs. `ingest.py`, `providers.py`, and `audio.py` connect source and AI services. `models.py`, `pipeline.py`, `renderer.py`, and `reader_assets/` provide the semantic-to-visual path. `skills/visual-synthesis/` holds reusable agent instructions and references.
