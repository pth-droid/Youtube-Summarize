# Use Distill

## Open the app

Double-click **Start Distill.cmd** in this folder. Leave its window open while pages are being made. The app opens at **http://127.0.0.1:8765**. Closing a browser tab keeps processing active. Closing the app window stops processing; saved work resumes after the next launch. An interrupted job may need up to 90 seconds to become available again.

This computer already has the app environment. For a new installation, install Python 3.12–3.14 first, then run `powershell -NoProfile -ExecutionPolicy Bypass -File .\setup-app.ps1`. Run `powershell -NoProfile -ExecutionPolicy Bypass -File .\start-app.ps1` to start it. These commands apply the script policy only to that process.

The app needs your signed-in Codex CLI to create new pages with your subscription. In a terminal, use `codex login` if the CLI asks you to sign in. The app uses the Codex sign-in available in the environment where you start it. A subscription allowance can pause processing. Check the job message and retry later when your allowance returns.

## Make your first page

1. The app opens **What do you want to make?** Choose **Interactive page** or **Lecture slides**. The saved default carries a **Default** tag. For slides, also choose a **Slide look**.
2. Under **Source**, keep **YouTube link** and paste a video link, or choose **Transcript file** or **Audio file**.
3. Select **Create interactive page** (or **Create lecture slides**), or press Enter in the link field. The app uses your saved settings. The Processing view shows progress.
4. Open the saved page from your Library.

Your language, knowledge level, and AI provider appear below the link. Select **Edit defaults** to change and save these settings. Open **Options for this page** to change them for one page or add a learning goal. Select **Use saved defaults** to reset those choices. API providers still need approval unless you enabled API use in Settings.

Select an idea to see its meaning, conditions, relationships, and original evidence. Open **Dig deeper** for saved child ideas. Use the source timestamp to open the video at that point. Plain text has no verified timestamps. AI claims can still be wrong; original passages and visible uncertainty help you inspect them.

If the source already has a saved page, open it or create a new version. A new version can use another language, goal, level, model, or provider. It keeps earlier versions.

## Interactive page or lecture slides

At the top of the start view, choose what to create: **Interactive page** or **Lecture slides**. Set the usual choice in **Settings → Default output**.

Lecture slides teach the same checked analysis as a talk you present to a group. The deck has a title, learning objectives, the central question, an agenda, one part per chapter, a summary, and a final slide with limits and the source. It has no quiz. Each content slide lists the times it comes from; a quote slide shows the speaker's original words. Inferences, added background and uncertain points keep their label. The lecture stage makes two or more extra AI requests after the analysis; it never re-reads the transcript.

The AI chooses each slide's structure: points, steps, a timeline, a comparison, parallel columns, a table, a pyramid, a funnel, stated figures or a quote. A figure is shown only when the cited ideas state it. The app then draws the slide with a layout from the slide-design library that fits the content: columns, cards, accent panels, timelines, arrows, pyramids, funnels, big numbers, tables and more, each in four variants. It rotates them so two neighbouring slides never share a frame. Re-rendering a deck keeps the same layouts.

Present with a click, the mouse wheel or trackpad, the arrow keys, Page Up/Down (a presenter remote) or the space bar. Each advance first reveals the slide's next point, then moves to the next slide; going back hides the last point, and an earlier slide comes back complete. **Shift** with an arrow skips the remaining points. **B** or **.** blanks the screen; any key brings the slide back. Press **N** for presenter notes, **F** for full screen (again, or Esc, to leave it), or open **Slides** to jump. Full screen works in the app and in an exported file. Choose the deck's look under the format cards, in **Slide look**: **Forest green** matches the app, and **Maroon and beige** sets deep maroon on beige paper (beige on deep maroon in dark mode). **Settings → Slide look** sets the starting choice. For a video that already has slides, making them in another look reuses the saved analysis and slide plan, so it needs no AI requests. Light or dark mode stays a choice while you present. **Print / PDF** prints one 16:9 slide per page. On a phone the slides read as a scrolling list.

When a YouTube video already has an interactive page, choosing lecture slides offers **Make lecture slides from it**. The saved analysis is reused when the language, level, goal, provider and model match, so only the lecture stage runs. The same applies in the other direction. **Create a new version** in a format the source already has always analyses again. **Export HTML** saves a deck as one offline file, like a page.

## Figures for processes and machines

When a source explains mechanisms or procedures, such as roasting or brewing coffee, the app can add up to four figures. They appear after the learning views on a page, and after the matching part in lecture slides:

- **Process**: the phases on one time scrubber, with quantity curves, how the subject changes (a coffee bean or a ground particle) and which compounds form or disappear. Drag the scrubber, select a phase, or select **Play**.
- **Apparatus**: a cutaway of a drum roaster, an espresso machine or a pour-over, with heat, air, water, gas, pressure and material flows. Turn each kind of flow on or off, pause the motion, or select a numbered part.
- **Control chart**: two quantities with named regions, such as extraction yield against strength.
- **What if**: raise or lower a setting and follow the effects the source states. It shows direction only, not size.
- **Scale ladder**: the same process from the machine down to molecules.

Every number shows where it comes from. Values the source states appear as dots, and the dashes between them only join them. Reference values that the source does not state carry a label. An illustrative shape hides its numbers. **Figure data** opens the same content as tables. The figure step makes one extra AI request, and only for sources with at least two mechanism or procedure ideas; switching between a page and slides reuses it.

In a process figure, select **Compare a roast log** and choose an Artisan `.alog` file, an Artisan CSV export, or a CSV with a time column. The file is read in your browser only; nothing is uploaded or saved. The app draws your bean and air temperatures next to the source's curve. It also computes the rate of rise from the bean temperature over 30 seconds, and marks dry end, first crack and drop.

## Captions and the spoken language

The app uses the captions in the language the video is spoken in. Subtitles in other languages are often translations, and an auto-dubbed video lists captions for every dubbed audio track, so they are not used unless you choose that language under **Options for this page → Source caption language**. When a video has captions in several languages, the app asks yt-dlp for the spoken language first. If no captions in that language exist, the page says the captions may be a translation.

If YouTube blocks the caption request, the app tries a second, free route through yt-dlp before it suggests paid transcription. The source then notes that its captions came through yt-dlp.

## When captions are not available

The app asks before it downloads audio or sends audio to a transcription service. Choose either route:

- Import a TXT, SRT, VTT, or transcript JSON file. The text is used as it is, with no cloud request. SRT, VTT, and timed JSON keep source times; VTT `<v Name>` tags and JSON `speaker` fields keep speaker names.
- Add a Soniox key in Settings and approve paid transcription for this source. Soniox is the default service.

You can also import an audio file, such as a meeting or lecture recording. Choose **Meeting** or **Lecture or talk** under the file. **Settings → Audio transcription** sets a service for each kind of recording: meeting recordings, lectures and talks, and YouTube videos without captions. All three start on Soniox. For example, keep Soniox for meetings, where speaker labels matter, and use Groq's free tier for single-voice lectures. The approval card shows which kind of recording it is and which service will receive it. The local copy waits for approval before cloud processing. Audio import accepts files up to 1 GB and sources up to six hours. FFmpeg and FFprobe must be available for audio preparation. YouTube audio download uses yt-dlp, which solves YouTube's JavaScript challenge with Deno, or with Node.js when Deno is missing. YouTube changes often: when captions or audio stop downloading, open **Settings → YouTube downloader**, select **Check for update**, then **Update yt-dlp**. The update installs the newest release from the Python Package Index into this app's environment only. A failed download names the cause, such as a bot check, an age restriction or an outdated yt-dlp, and **Diagnostic details** keep yt-dlp's last lines. YouTube may still block a download. Transcript import remains the recovery route.

Soniox separates speakers. Each passage of a meeting gets a label such as **Speaker 1** or **Speaker 2**, and the reader and the analysis keep it. The labels are numbered by first voice; Soniox does not know names. A recording with one voice, such as a lecture, gets no label. The app uploads the whole recording once, as 16 kHz mono FLAC, so a person keeps one label for the entire recording. Soniox accepts up to five hours per file and bills by audio duration (USD 0.10 per hour on its published price list in October 2026). After success the app deletes the uploaded audio and transcript from Soniox; Soniox removes anything left after 30 days. If processing stops, the saved Soniox request resumes on retry without a second upload.

To use Groq Whisper instead, choose it for that kind of recording under **Settings → Audio transcription**. Groq has a free allowance but returns no speaker labels. Groq's free allowance can require a wait for long recordings. The app saves each completed audio section. It cannot inspect or impose your Groq billing plan. Check the plan in your Groq account before approval. A paid account needs the explicit paid route and approval. Source audio is removed after successful transcription by default. After failure or cancellation, temporary audio becomes eligible for cleanup 24 hours later while the worker is running. Select **Delete temporary audio** for earlier removal, or enable **Keep source audio** before creating the job.

## Providers and charges

Codex is the default. It uses your existing subscription through the local CLI. It does not use an OpenAI API key.

Claude is the second subscription option. It uses the locally installed Claude Code CLI with your Claude subscription sign-in (run `claude`, then `/login`, once). The app removes `ANTHROPIC_API_KEY`, auth tokens, custom endpoints and cloud routing from its environment, so a Claude call is never billed to an API account; a `claude setup-token` subscription token is kept. Each call runs without tools, MCP servers, skills, user settings or saved sessions, and the CLI validates the answer against the stage's JSON schema. It counts against your plan's usage limits; when a limit is reached, the job pauses with a usage message. Leave the model empty to use the CLI default, or set `claude_code_model` in preferences.

To use your own provider, open **Settings → Provider access → Add connection**. Enter a connection name, endpoint, exact model ID, and API format. Add a key if needed. You can save several models from the same provider. Open a saved connection to edit it or select **Use as default**. Read [PROVIDER_CONNECTIONS.md](PROVIDER_CONNECTIONS.md) for connection options.

Approve API use for each page, or enable the API default in Settings. Provider failures do not switch to other providers automatically. Existing DeepSeek access remains available when configured. Saved keys stay in the operating system credential store. Saving a connection sends no AI request.

Keys use the operating-system credential store. They do not appear in saved pages or backups. Environment variables `DEEPSEEK_API_KEY`, `SONIOX_API_KEY`, and `GROQ_API_KEY` are also supported. Removing a saved key does not remove a key supplied by an environment variable.

Open **Generation details** on a completed job to see reported token usage. These records describe the latest processing run; earlier work reused from checkpoints may be missing. Subscription allowance and billed cost are shown as unknown or unavailable because the app cannot read those account details.

## Save, export, and back up

Select **Export HTML** to save one interactive file. It works in a local browser without the app or an internet connection. Opening the original video still needs internet. Select **Print / PDF** in the reader to use your browser's print dialog.

Your default Windows library is stored at `%LOCALAPPDATA%\VisualLearning`. It contains one SQLite database, saved interactive HTML pages, source transcripts, evidence and analysis records, processing jobs, and your preferences. SQLite needs no database server. The Settings view shows the exact location. Keep the database and files together.

To change the saved folder, open **Settings ? Your saved library**. Paste a full folder path, for example `D:\MyLearningLibrary`, then select **Change library folder**. Choose a new or empty folder. Finish or cancel running, queued, and quota-waiting jobs first. The app copies the complete library, checks the copied database, and uses the selected folder immediately. The original folder stays as a backup, including a consistent `library-before-move-*.sqlite3` snapshot and `LIBRARY_MOVED.txt` restore instructions. API keys stay in the credential store.

Your folder choice is remembered outside the library in `%LOCALAPPDATA%\VisualLearningConfig\library-location.json`. The normal launcher uses it after restart. A deliberate `--data-dir` argument or `DISTILL_DATA_DIR` environment variable takes priority; an old copied library redirects to its new location. Keep the original backup until you have opened the saved pages in the new location. If a removable drive is unavailable, reconnect it before starting. Do not use a system folder, credential folder, or a folder inside the current library.

In Settings, select **Download library backup** after processing has finished or has been cancelled. The ZIP contains the library database, source files, pages, jobs, and preferences. It excludes API keys. A large audio library can make the backup take time; avoid other library changes until the download finishes.

To restore, close the app and its worker. Copy the ZIP's `library.sqlite3` and `jobs` folder into an empty library folder. Start with that folder using `.venv\Scripts\python.exe -m distill --data-dir D:\MyLearningLibrary`. Save provider keys again if you moved to another computer. Keep your original backup until you have opened the restored pages.

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
