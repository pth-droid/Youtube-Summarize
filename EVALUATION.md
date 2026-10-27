# V1 evaluation evidence

Checked locally on 2026-10-04, with processing evidence updated on 2026-10-05. This report separates real source evidence from authored test fixtures. It is not a claim that every video has a verified finished learning page.

## Real source retrieval

All eight videos supplied by the owner returned timestamped captions on this computer. The saved records are under `.feasibility/`. The result establishes local caption access on the tested network; cloud-hosted retrieval remains unverified.

| Owner category | Video ID | Caption language | Caption span |
|---|---|---|---|
| Podcast/discussion | `0qqW3vxOC-g` | en-US | 09:25 |
| Podcast/discussion | `lNWhbbAM59Y` | en-US | 24:35 |
| Podcast/discussion | `-oladUKkhgo` | vi | 44:38 |
| Podcast/discussion | `BfEfD0BRfDw` | vi | 26:51 |
| Podcast/discussion | `jrnGl43pQl8` | vi | 13:43 |
| Review | `d1X7LgYpRds` | en | 10:39 |
| Tutorial | `jLKQp4SgGr0` | en | 59:43 |
| Tutorial | `Blb6y9Um1r0` | vi | 44:37 |

These are last-caption end times, not measured video durations. The language belongs to the selected caption track and does not independently establish the original spoken track. None of these eight full sources has a completed, independently reviewed learning page recorded by this evaluation.

An additional source, `L_Guz73e6fw`, returned 3,206 English snippets spanning 02:23:48. It provides a real long-transcript input. Retrieving that input is distinct from successfully synthesizing the complete source.

## Real Codex output

The Codex subscription connector returned structured Vietnamese JSON in the real access smoke check. No OpenAI API key was used.

The saved `.feasibility/pipeline-short/` page was generated from the first 24 caption snippets of `L_Guz73e6fw`, ending at 01:08.88. It is a feasibility excerpt, not a summary of the complete 2-hour-23-minute podcast. The earlier saved generation record reports 120.9 seconds for its recorded run; it is not a normal latency estimate for complete videos, and cached earlier work may be excluded.

Independent reading of its original captions and knowledge records found these useful properties:

- The Vietnamese explanation preserves AGI, OpenAI, DeepMind, GPT4, ChatGPT, DALL·E, and Codex.
- It describes the alleged 2015 ridicule as the speaker's account, with quoted caption support.
- The scientist/reporter anecdote is presented as one reported example, not proof of a whole industry's attitude.
- It does not infer that later products caused reduced ridicule, or that AGI was achieved.
- It retains uncertainty about unnamed speakers and about how widespread the reactions were.
- The introduction's CEO/product information remains attributed to the source, rather than presented as independently checked current facts.

The stored headline was marked uncertain and does not contain the newer dedicated headline-evidence field. This earlier artifact is not proof that the latest headline-grounding workflow has passed a real complete-source run. The current implementation requires dedicated headline support and adds further cache validation.

The long source has ten analysis windows. The first-window checkpoint covers 340 of its 3,206 snippets and has been re-reviewed with migration complete. The complete probe is paused behind the production job; no completed long-source page is available for independent semantic inspection. A measured review-input reduction on the real first window reduced 59,113 characters to 46,205 characters, below the 49,396-character review budget. All 337 original supporting passages were preserved. This establishes the input reduction and checkpoint behavior, not complete-source learning quality.

An additional production source, Vietnamese finance discussion `2QMUoUrs2bg`, contains 771 caption snippets spanning 29:40.6. Its job `af8261c289ed48efa48cce0adeacd578` failed at 18:05 UTC on 2026-10-04 after three bounded extraction retries on the second source window. The failures involved malformed citation identifiers, including `s000629 text`, `s000669 text`, and `s000682 text`; the final attempt also omitted a required source identifier. The source and the first 351-snippet checkpoint remain saved. This run did not fail because of quota, timeout, or authentication, and used no paid API calls. It produced no completed page.

On 2026-10-05, approved paid DeepSeek retries of that saved job exposed further connector limits. The first recorded length failure reached the app's 16,384 output-token cap. A second run at 32,768 tokens also ended at the cap; DeepSeek reported all 32,768 as reasoning tokens, with no room for the JSON answer. The connector now disables DeepSeek thinking mode for structured work and uses 12,000-character extraction windows. Subsequent non-thinking requests no longer showed the length failure, but the first extraction window still failed after three validation attempts: its last output had an unsupported unit kind and several evidence lists longer than the schema's 12-source-ID limit. A separate request returned unreadable JSON. The app now records bounded diagnostics without keys, transcript text, or raw provider responses, retries unreadable JSON within the three-attempt stage limit, and restates kind/evidence limits next to the source input. A later live run passed those field checks but failed the exact-quote check. Localized quote-repair feedback was added; its next live attempt ended in an interrupted connection, so that repair is not proven with DeepSeek. No DeepSeek page was published; paid amount is unavailable from the app.

The same production job subsequently completed through the default Codex subscription provider. Generation `277031c00d2e4bbfa78c1b1e61f91a1f` preserves all 771 original source snippets and passed `validate_bundle`, including exact evidence quotes and complete source coverage. The saved model contains four overview ideas, 64 total ideas, 40 relationships, and two concept-map views. It retains the speaker's conditional interest-rate scenarios and distinguishes the retail and interbank markets. Headless Playwright checks passed for opening the real saved page, node evidence, transcript highlighting, video timestamp navigation, HTML export, and offline mobile use without JavaScript errors or horizontal document overflow. This establishes a complete 29:40-source run, not the pending 1–3-hour quality acceptance.

The Jobs view now preserves expanded diagnostic panels during polling and avoids replacing unchanged job details. A headless Playwright regression passed while repeated polling changed the job record. Codex CLI failures also retain safe exit/category metadata. The latest focused Python run passed 83 connector/learning checks, including localized quote-repair feedback.

The subsequent pipeline change constrains citation identifier format in the output schema and provides exact, bounded feedback for invalid identifiers. Sixteen targeted `tests_app/test_learning.py` checks passed. A small authored subscription-only Codex probe accepted the new strict identifier schema, returned the exact original `s000265` identifier and quote, and passed validation. Evidence is saved under `.feasibility/source-id-guard/`. This fixture is not a real video or proof of complete-source educational quality. The change was not loaded into the already running production worker, and that worker was not restarted or the failed job retried as part of this check.

The remaining evaluation must compare completed outputs' major ideas, omitted caveats, argument differences, mechanisms, technical terms, and source navigation against complete original transcripts. A working deterministic renderer cannot establish that an LLM retained the important meaning of a long source.

## Authored fixtures and browser checks

`tests_app/learning_fixture.py` and `tests_app/grammar_fixture.py` contain authored coffee examples. Their visible labels state that they are not real video summaries. The linked video ID is used to check link format only; the authored coffee text is not evidence about that video.

Seven visual grammars were exercised offline at desktop width 1,280 and mobile width 390: concept map, causal graph, process, argument map, hierarchy, comparison, and timeline. Targeted headless Playwright checks covered original evidence, transcript highlights, canonical timestamp links, process order, nested children, objection placement, comparison cells, and page width. The comparison table uses horizontal scrolling on mobile. The final combined browser run also checks causal arrow markers and reaching the last comparison column.

Saved screenshots are under `.feasibility/screenshots/`. Independent visual inspection found readable cards and Vietnamese accents, no clipped main library content, and a visible causal arrow on the desktop fixture. The mobile comparison needs horizontal exploration to show all choices. These checks establish interaction and rendering behavior for fixtures, not educational accuracy on real sources.

Connector contract checks use fake cloud responses and local subprocess/audio fixtures to verify contracts, approval, source identity, recovery, cancellation, uncertain request handling, and timestamp preservation. The real DeepSeek request findings are recorded above; real Groq access remains unverified.

## Unverified release conditions

- Real approved DeepSeek requests reached the configured model, but no complete source-grounded page passed validation. Actual billed cost and successful DeepSeek teaching quality remain unverified.
- No YouTube audio was downloaded and no audio was uploaded to Groq. Free-account status, Vietnamese recognition, speaker-heavy audio quality, and the two Whisper-model comparison remain unverified.
- No complete learning outputs for all eight supplied sources have been independently evaluated.
- Complete 1–3-hour synthesis quality, normal processing time, and peak resource use remain unverified. The production 29:40-source run completed; the separate long-source probe remains unfinished.
- Private online hosting, owner login, cross-device storage, and hosted Codex subscription use are later work and are not validated by local checks.

The local V1 can be assessed through its implemented flows and deterministic checks. A final claim of validated long-transcript learning quality must wait for complete real-source output review. See `FEASIBILITY.md` for connector details and `MASTER_PLAN.md` for the agreed acceptance criteria.
