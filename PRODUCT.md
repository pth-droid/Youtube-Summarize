# Product

<!-- impeccable:product-schema 1 -->

> Written on 2026-11-03 without an interview: the user asked for an end-to-end redesign and said not to stop and ask. Facts come from the code, APP_GUIDE.md and the user's notes; lines marked *(inferred)* are assumptions to confirm.

## Platform

web

## Users

- One owner-operator who runs Distill on their own Windows PC and opens it in a desktop browser, sometimes on a phone over Tailscale. *(inferred from the setup scripts and Tailscale share)*
- They learn from YouTube videos, transcripts and recordings of meetings, lectures and talks, in Vietnamese and English, often about coffee roasting and running a café. *(inferred from fixtures and the Lighthouse brand notes)*
- Lecture decks are presented by that person to a group of people, on a projector or a TV mirrored from a phone.

## Product Purpose

Distill turns one source (a YouTube link, a transcript file or an audio file) into either an interactive learning page or a lecture slide deck. The page shows the big picture first, how ideas connect, and the original evidence with timestamps. The deck teaches the same checked analysis to a group. Everything is saved in a local library that can be opened again, exported as one offline HTML file, or shared to a phone.

Success: paste a link, get a trustworthy overview with its evidence, and come back to it later.

## Positioning

Overview first, evidence always within reach: every idea keeps the source passage and timestamp it came from, uncertainty and inference stay labeled, and the library stays on the user's computer. It runs on the AI subscriptions the user already has (Codex, Claude) or their own API connections.

## Operating Context

- Workflow: choose Interactive page or Lecture slides, add a source, follow the job through Processing (captions, analysis, checks, saving), approve paid or uploaded audio transcription when asked, then explore or present from the Library.
- Jobs run in a local worker; the browser can close while the app keeps working.
- Settings hold defaults (language, knowledge level, AI provider, slide look), AI connections and keys, transcription services per kind of recording, the library folder, backup and the yt-dlp updater.
- Slide looks can be customized in a look editor with projector contrast checks.

## Capabilities and Constraints

- FastAPI server with plain HTML, CSS and JavaScript; no build step or framework.
- Strict Content Security Policy: no inline styles or scripts in markup, images only from the app or data URIs, no external fonts or hosts. Fonts must be served from `distill/web/fonts`.
- Saved pages and decks render in a sandboxed iframe and are portable documents with their own styles; `theme.js` is embedded in them, so its storage key and message types must not change.
- Vietnamese and English content; Vietnamese diacritics must render well.
- Playwright tests address controls by id, role and accessible name.
- Paid or uploading actions always need the user's explicit approval in the UI.

## Brand Commitments

- Name: Distill. Line: "Overview first. Evidence always within reach."
- The Lighthouse café brand (D:\Working\lighthouse-brand-foundation) binds only the Maroon and beige slide look, not the workspace.
- Visual reference pinned by the user on 2026-11-03: the Dribbble shot "Bike Rental & Navigation App UI Design" by Nixtio (immersive aerial canvas, frosted round controls, floating cards, amber accents, route lines).

## Evidence on Hand

- Real saved pages and decks exist only in the user's own library; the test server seeds fixture pages ("Reader interaction fixture", "Coffee process figures").
- No thumbnails or cover images are stored for sources, and the CSP blocks YouTube thumbnails. Any cover art must be generated in the app.

## Product Principles

1. The source stays visible: evidence, timestamps and uncertainty are never hidden for the sake of polish.
2. Nothing paid or uploaded happens without a clear yes.
3. Local first: the library, keys and preferences stay on this computer.
4. Start fast: a link and one action are enough; options wait until asked for.
5. Work is never lost: progress is saved as it goes and can resume.

## Accessibility & Inclusion

- Keyboard use throughout, visible focus, and contrast that holds on a projector for decks. *(inferred from the look editor's checks)*
- Respect reduced motion.
