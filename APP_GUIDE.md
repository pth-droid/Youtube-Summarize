# Use Visual Learning

## Open the app

Double-click **Start Visual Learning.cmd** in this folder. Leave its window open while pages are being made. The app opens at **http://127.0.0.1:8765**. Closing a browser tab keeps processing active. Closing the app window stops processing; saved work resumes after the next launch. An interrupted job may need up to 90 seconds to become available again.

This computer already has the app environment. For a new installation, install Python 3.12–3.14 first, then run `powershell -NoProfile -ExecutionPolicy Bypass -File .\setup-app.ps1`. Run `powershell -NoProfile -ExecutionPolicy Bypass -File .\start-app.ps1` to start it. These commands apply the script policy only to that process.

The app needs your signed-in Codex CLI to create new pages with your subscription. In a terminal, use `codex login` if the CLI asks you to sign in. The app uses the Codex sign-in available in the environment where you start it. A subscription allowance can pause processing. Check the job message and retry later when your allowance returns.

## Make your first page

1. The app opens **Learn something new**. Paste a YouTube video link.
2. Select **Create learning page**, or press Enter in the link field. The app uses your saved settings. The Processing view shows progress.
3. Open the saved page from your Library.

Your language, knowledge level, and AI provider appear below the link. Select **Edit defaults** to change and save these settings. Open **Options for this page** to change them for one page or add a learning goal. Select **Use saved defaults** to reset those choices. Transcript and audio imports are available below the options. API providers still need approval unless you enabled API use in Settings.

Select an idea to see its meaning, conditions, relationships, and original evidence. Open **Dig deeper** for saved child ideas. Use the source timestamp to open the video at that point. Plain text has no verified timestamps. AI claims can still be wrong; original passages and visible uncertainty help you inspect them.

If the source already has a saved page, open it or create a new version. A new version can use another language, goal, level, model, or provider. It keeps earlier versions.

## When captions are not available

The app asks before it downloads audio or sends audio to Groq. Choose either route:

- Import a TXT, SRT, VTT, or transcript JSON file. SRT, VTT, and timed JSON keep source times.
- Add a Groq key in Settings, confirm your account uses free billing, and approve audio for this source.

You can also import an audio file. The local copy waits for approval before cloud processing. Audio import accepts files up to 1 GB and sources up to six hours. FFmpeg and FFprobe must be available for audio preparation. YouTube audio download uses yt-dlp; some videos also need its supported JavaScript runtime and challenge components. YouTube may still block a download. Transcript import remains the recovery route.

Groq's free allowance can require a wait for long recordings. The app saves each completed audio section. It cannot inspect or impose your Groq billing plan. Check the plan in your Groq account before approval. A paid account needs the explicit paid route and approval. Source audio is removed after successful transcription by default. After failure or cancellation, temporary audio becomes eligible for cleanup 24 hours later while the worker is running. Select **Delete temporary audio** for earlier removal, or enable **Keep source audio** before creating the job.

## Providers and charges

Codex is the default. It uses your existing subscription through the local CLI. It does not use an OpenAI API key.

To use your own provider, open **Settings → Provider access → Add connection**. Enter a connection name, endpoint, exact model ID, and API format. Add a key if needed. You can save several models from the same provider. Open a saved connection to edit it or select **Use as default**. Read [PROVIDER_CONNECTIONS.md](PROVIDER_CONNECTIONS.md) for connection options.

Approve API use for each page, or enable the API default in Settings. Provider failures do not switch to other providers automatically. Existing DeepSeek access remains available when configured. Saved keys stay in the operating system credential store. Saving a connection sends no AI request.

Keys use the operating-system credential store. They do not appear in saved pages or backups. Environment variables `DEEPSEEK_API_KEY` and `GROQ_API_KEY` are also supported. Removing a saved key does not remove a key supplied by an environment variable.

Open **Generation details** on a completed job to see reported token usage. These records describe the latest processing run; earlier work reused from checkpoints may be missing. Subscription allowance and billed cost are shown as unknown or unavailable because the app cannot read those account details.

## Save, export, and back up

Select **Export HTML** to save one interactive file. It works in a local browser without the app or an internet connection. Opening the original video still needs internet. Select **Print / PDF** in the reader to use your browser's print dialog.

Your default Windows library is stored at `%LOCALAPPDATA%\VisualLearning`. It contains one SQLite database, saved interactive HTML pages, source transcripts, evidence and analysis records, processing jobs, and your preferences. SQLite needs no database server. The Settings view shows the exact location. Keep the database and files together.

To change the saved folder, open **Settings ? Your saved library**. Paste a full folder path, for example `D:\MyLearningLibrary`, then select **Change library folder**. Choose a new or empty folder. Finish or cancel running, queued, and quota-waiting jobs first. The app copies the complete library, checks the copied database, and uses the selected folder immediately. The original folder stays as a backup, including a consistent `library-before-move-*.sqlite3` snapshot and `LIBRARY_MOVED.txt` restore instructions. API keys stay in the credential store.

Your folder choice is remembered outside the library in `%LOCALAPPDATA%\VisualLearningConfig\library-location.json`. The normal launcher uses it after restart. A deliberate `--data-dir` argument or `VISUAL_LEARNING_DATA_DIR` environment variable takes priority; an old copied library redirects to its new location. Keep the original backup until you have opened the saved pages in the new location. If a removable drive is unavailable, reconnect it before starting. Do not use a system folder, credential folder, or a folder inside the current library.

In Settings, select **Download library backup** after processing has finished or has been cancelled. The ZIP contains the library database, source files, pages, jobs, and preferences. It excludes API keys. A large audio library can make the backup take time; avoid other library changes until the download finishes.

To restore, close the app and its worker. Copy the ZIP's `library.sqlite3` and `jobs` folder into an empty library folder. Start with that folder using `.venv\Scripts\python.exe -m visual_learning --data-dir D:\MyLearningLibrary`. Save provider keys again if you moved to another computer. Keep your original backup until you have opened the restored pages.

## Recovery

Processing saves completed source and analysis stages. A stopped job offers **Retry saved work** or **Import a replacement transcript**. Changing the AI provider keeps the original source and starts compatible analysis again. Changing a YouTube caption language clears earlier source work and audio approval. To change an imported source's transcription language, import a new source.

Quota waits resume at the reported time. Temporary connection failures have two automatic retries. An interrupted cloud response can already have used quota or paid usage, so that case requires manual retry. Cancellation stops subsequent work when the active request returns or the local process can be stopped.

For a failed job, expand **Diagnostic details** when available. DeepSeek limit errors show the provider, model, analysis stage, source window, request size, output limit, and returned token counts. Validation failures show the failed field and rule. The log does not contain API keys, transcript text, or raw model responses. Earlier failed calls cannot gain missing provider usage data after the fact.

If the app cannot start because the port is in use, run `powershell -NoProfile -ExecutionPolicy Bypass -File .\start-app.ps1 -Port 8767`. To run without opening a browser, add `-NoBrowser`.

## What comes later

This version stores interactive learning pages. Digging deeper opens saved explanations. Live AI questions, owner login, hosted processing, cross-device sync, and general article or paper input remain later stages of the master plan. The web, worker, source, provider, and renderer are separate modules to support those stages. Local SQLite files are not a cloud sync service.

## Developer verification

Install the check tools with `.venv\Scripts\python.exe -m pip install -r requirements-app-dev.txt`, then run `.venv\Scripts\python.exe -m pytest app_tests tests_app -q`.

For browser checks, run `npm.cmd install`, `npx.cmd playwright install chromium`, then `npx.cmd playwright test`. These tests use headless Playwright Test, an isolated temporary library, authored semantic fixtures, and saved real-source artifacts when available. They do not send paid AI requests or audio to cloud services.

Read [BUILD_STATUS.md](BUILD_STATUS.md) for measured results and remaining limits. Read [MASTER_PLAN.md](MASTER_PLAN.md) for the product design.
