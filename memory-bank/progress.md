# Progress

## Done

### Phase 1 — Scaffold + memory bank (2026-10-11)

- Git repository initialised (no commits yet), MIT `LICENSE`, root `.gitignore`, `README.md`.
- `apps/desktop`: Tauri 2 + React/TS shell. One Rust command (`app_info`) displayed by the window. `hud/` module placeholder.
- `engine`: Python project with `audio`, `diarization`, `memory`, `actions` packages. FastMCP server with one tool (`recall_health`) and a `recall-actions` console script.
- `memory-bank/` (6 files) and `knowledge/history/` (2 logs) created.
- Verified: `cargo check` and `cargo clippy -- -D warnings` clean, `pnpm typecheck` clean, `uv run pytest` 1 passed, `pnpm tauri dev` window shows `desktop v0.1.0`, no `unsafe`, SPDX header on every source file.

### Phase 2 — Audio pipeline and real-time transport (2026-10-11)

- Alignment: author name corrected to "Yüksel Alp Çiğtekin" in `engine/pyproject.toml`; engine pinned to Python 3.12.
- `audio`: microphone capture (sounddevice), system audio capture (ScreenCaptureKit), utterance chunker, faster-whisper transcriber with word timestamps.
- `diarization`: source-based speaker labels; pyannote adapter and word-to-turn assignment.
- `transport`: loopback WebSocket server with Origin allowlist.
- `pipeline`: `recall-engine` entry point; settings from environment (`engine/.env.example`).
- `hud`: live transcript feed in the desktop window with auto-reconnect.
- Verified: `uv run pytest` 21 passed (includes a real Whisper transcription of synthesised speech), `pnpm typecheck` clean, `cargo clippy -- -D warnings` clean, live run on macOS showed a spoken sentence in the app window.
- Not verified: pyannote against the real model (no token yet); a real multi-person meeting; long-running sessions.

### Phase 3 — Memory and engine lifecycle (2026-10-11, branch `feat/phase-3-memory-sidecar`)

- Phases 1 and 2 committed and pushed to `origin/main` (private GitHub repo).
- `memory`: tenant/project-scoped vector store on embedded Qdrant, local multilingual embeddings, search CLI.
- `pipeline`: stores every published segment when a scope is configured; clean stop on SIGTERM or closed stdin.
- `desktop`: Rust `engine.rs` starts the engine with the app and stops it with the app.
- Verified: `uv run pytest` 40 passed; `cargo test` 4 passed; clippy and typecheck clean; live run stored a spoken sentence and found it only under its own tenant and project; the app launched the engine by itself and the engine exited after the app was force-killed.
- **Not done: real pyannote check.** `engine/.env` with `HF_TOKEN` did not exist on this machine, so the model has still never been run.

### Phase 4 (part) — Fact-check HUD (2026-10-11, branch `feat/phase-4-fact-check-hud`, uncommitted)

- Phase 3 committed and pushed; PR #1 open against `main`.
- `factcheck`: figure extraction and the contradiction rule; `pipeline` checks each segment before storing it; alerts over the WebSocket; floating overlay window with Tailwind.
- Verified: `uv run pytest` 73 passed; `cargo test` 4 passed; clippy and typecheck clean; live run: saying "$35,000" and then "$50,000" about the budget produced the alert in the engine log and the overlay card on screen.
- Not verified: clicking dismiss and the 30 s auto-dismiss (no UI automation access); real meetings; false-positive rate beyond the 17 calibration pairs.
- Not started (blocked): speaker clustering (no `HF_TOKEN`), action tools (no credentials, no LLM for action-item extraction).

### Phase 5 (part) — GitHub issue action (2026-10-12, branch `feat/phase-5-github-action`, uncommitted)

- Phase 4 committed and pushed; PR #2 open, stacked on PR #1.
- `actions`: propose-only MCP tools, SQLite action queue, human approval, GitHub issue creation, review CLI; desktop panel with Approve/Reject.
- Verified: `uv run pytest` 91 passed; `cargo test` 6 passed; clippy and typecheck clean. Live: an issue proposed through the MCP tool was refused without confirmation, created on GitHub after approval (issue #3, closed afterwards), and a second approval was refused. The desktop panel displayed a queued proposal.
- Not verified: pressing Approve/Reject in the desktop window (no UI automation access).
- `diarization`: stable speaker names. The model terms were accepted on 2026-10-12, so pyannote ran for real for the first time. Each speaker's turns in an utterance are embedded with the pipeline's voice model and matched against the voices heard so far (`SpeakerTracker`, cosine 0.5).
- Verified with the real model on pyannote's public two-person sample (played twice, plus two synthetic voices, cut by the engine's own chunker): 4 names for 4 voices, 87% of speech under the right name, 23 s of CPU for 103 s of audio on an M1. Through `Engine.process` with Whisper, both people kept their names across both passes.
- Known limit: in utterances under about 10 s the model often hears two people as one, so that utterance gets a single name. Diarizing a 60 s sliding window fixed this in tests but took about 50 s per utterance, so it was dropped.
- Not verified: speaker names on live system-audio capture or in a real meeting.
- Not started: LLM action-item extraction (no LLM configured); Jira, Slack/Discord, Calendar tools (no credentials).

### Phase 6 (part) — Integration (2026-10-12, branch `feat/phase-7-competitor-features`, PR #6)

- Phase 5 committed and pushed; PR #4 open, stacked on PR #2.
- `hud`: transcript lines are split per speaker turn (`speakerTurns`).
- `actions`: Slack message (one configured incoming webhook) and Google Calendar all-day deadline (refresh-token OAuth, configured calendar) behind the same approval gate; propose tools refuse when the connector is not configured; the review panel and CLI show all three kinds.
- Verified live through the desktop app: capture, speaker names, memory with tenant isolation, fact-check alert, proposal queued and shown.
- During that run the queued Slack test proposal was approved in the app window by someone at the Mac (not by the assistant). It went to a made-up webhook path; Slack answered HTTP 302 and the failure was recorded without the URL.
- Not verified: Slack and Calendar against the real services; any step from transcript to proposal (none exists).
- Jira Cloud connector (2026-10-14): Tasks only, project-key allowlist, `*.atlassian.net` sites only, token never in errors or repr.

### Phase 7 (part) — Competitor features (2026-10-14, branch `feat/phase-7-competitor-features`, PR #6)

- `llm` + `summary` + `recall-summarize`: summary, decisions and action items from any OpenAI-compatible provider (Groq, Gemini, OpenRouter, Mistral, Ollama, LM Studio, OpenAI, custom) or Claude via the Anthropic SDK (`claude` extra); replies parsed as untrusted data; `--propose` queues through `actions/proposals.py`, the same validation the MCP tools use.
- `audio/transcriber`: `RECALL_ASR_BACKEND` with an mlx-whisper backend (`apple` extra). Parakeet was measured (1.00 s per 8 s piece, no Turkish) and dropped.
- `live_controls` + transport: typed notes and speaker renames from the desktop app; notes are "Note" lines in the transcript, notes file and memory.
- `privacy`: redaction of e-mails, phones, cards, IBANs, keys and spoken passwords before memory and notes; `RECALL_RETENTION_DAYS`; FileVault warning.
- `transcribe_cli`: VTT, `--watch`, `--remember` (content-hash meeting ids, so re-imports replace), creates missing output folders.
- `library` + desktop "Past meetings" view: search across meetings, per-meeting filter, click-to-play for linked recordings (asset protocol scoped per file), "Summarize with AI".
- Desktop tests now run with vitest (`pnpm test`).

### Phase 8 — Product completion (2026-10-15, branch `feat/phase-8-product`, PR #7)

- CI (GitHub Actions): ruff 0.17.0 + locked uv sync + pytest on Linux; pnpm typecheck/vitest/build; clippy -D warnings + cargo test on macOS. It caught a real bug (Claude client imported the SDK even when injected).
- Settings screen: schema in `settings.rs`, values in a 0600 JSON file, secrets in the Keychain (never returned to the webview), checked by `recall-check-config`, engine restarted on save.
- Packaging: `pnpm bundle` ships engine sources + uv.lock + checksum-verified uv; first launch installs managed Python 3.12 into the app data folder.
- `session.py`: meeting lifecycle. End (user or idle) → merge duplicate speakers → summary into notes → auto-proposals → next meeting. Ask over WebSocket. Recording (mixed WAV). Calendar titles.
- AI fact check (`factcheck/semantic.py`), opt-in, cooldown-limited.
- Auto-start: `recall-detect-call` (CoreAudio via PyObjC, no Rust `unsafe`) + Rust supervisor.
- Windows/Linux system audio via `soundcard` loopback (fake-tested only).

### Phase 9 — Experience (2026-10-15, branch `feat/phase-9-experience`, stacked on #7)

- Voices remembered across meetings; brief from earlier meetings when a calendar meeting starts; first-run checklist; recap e-mail to attendees (Gmail, approval-gated).
- Notes start with YAML properties (Obsidian); `notion` target creates a summary page under one configured parent page after approval.
- Live action items (opt-in, an AI call at most every 3 min); talk time / longest turn / interruptions per speaker in the notes and the app.
- `RECALL_REQUIRE_DISK_ENCRYPTION`: nothing stored unless FileVault is on.
- Auto-update (Tauri updater, key in `~/.tauri/continuum-updater.key`) and `release.yml` on `v*` tags; call detection on Windows (registry) and Linux (`pactl`).
- Component click tests (jsdom + mocked IPC); CI coverage floors 70% engine / 50% desktop lines (measured 78% / 54%).
- Verified: 325 pytest, 24 vitest, 16 cargo, clippy, ruff; signed release build produced the updater archive + signature. Not verified: Notion/Gmail against real services, Windows/Linux call detection on real machines, an update served from a real GitHub release.

## Phase 10 (spec complete, `feat/phase-10-spec-complete`)

- Project picker in the meeting bar; code context hints (`RECALL_CODE_DIRS`); commitments and hesitations in the notes, with an optional workload check against Jira (and its open sprint), GitHub and GitLab issues; optional AI hesitation pass (`RECALL_LLM_HESITATIONS`).
- Google connected from Settings (PKCE); system audio optionally limited to meeting apps (`RECALL_MEETING_APPS_ONLY`, macOS).
- `recall-transcribe --summarize`; `recall-import-docs` puts Markdown/text/PDF documents in project memory so fact checks cite them.
- Fact checks read spelled-out numbers and dates with a month name; turns pyannote gives one speaker are re-split against known voices.
- GitLab issues as approval-gated actions; long utterances cut at a quiet moment; Info.plist and audio-input entitlement for the notarised app.
- Verified: 398 pytest, desktop action tests, 17 cargo, ruff; ad-hoc signed `.app` with hardened runtime. Not verified: the AI hesitation pass against a real model, GitLab/GitHub workload against real services, notarisation (needs Apple secrets).

## Phase 11 (polish, `feat/phase-11-polish`, stacked on phase 10)

- Outside services retried on 429 (Retry-After) and, for reads, 502-504 (`recall.net`); a change is never repeated after a server error.
- `recall-check-connections` and the Settings **Test connections** button: read-only sign-in to GitHub, GitLab, Jira, Notion, Google, Hugging Face (plus each allowed repo/project) and a one-word AI reply.
- **Add documents…** in the meeting bar imports through the running engine (live command `import_documents`).
- First-run checklist steps are filled in and saved in place (folder picker for notes; no key for local AI).
- CI runs the engine tests on Ubuntu, macOS and Windows.
- Workload lookups follow GitHub/GitLab pagination (up to 50 pages). Browser extension (`apps/browser-extension`, MV3) sends only the meeting tab's audio to the engine (`tab` source, ws://127.0.0.1:8766, extension origins only); with it on, browsers are left out of macOS system audio.
- Verified: 409 pytest, 38 vitest, 17 cargo, clippy, ruff; connection check against the real GitHub, GitLab, Groq and Hugging Face APIs (wrong tokens rejected with readable reasons). Not verified: the Windows CI run (not pushed yet).

## Phase 12 (toward 10/10, `feat/phase-12-ten`, stacked on phase 11)

- Turkish: `RECALL_LANGUAGE` (en/tr) for the app, notes, hints, AI replies; Turkish promises/doubts/dates; a test fails on any untranslated UI or settings text.
- Live translation captions (`RECALL_TRANSLATE_TO`); follow-up e-mail (plain text, copy or mailto, Gmail proposal); meeting templates (`RECALL_MEETING_TEMPLATE`, auto from title).
- Hear only the meeting app on Windows (WASAPI process loopback via comtypes) and Linux (`parec --monitor-stream`), both falling back to all system audio; shared `audio/follow.py` loop.
- Shared-slide fact checks (`RECALL_SCREEN_FACT_CHECK`, macOS Vision OCR of meeting windows only); Firefox extension (WebRTC track tap on meeting sites, web-ext lint clean); diagnostics report and file log (`~/.recall/logs/engine.log`).
- Verified: 456 pytest, 46 vitest, extension node tests, 17 cargo, clippy, ruff; real slide OCR of a "Google Meet" Safari window (Gmail in another browser window correctly ignored); comtypes API names checked against 1.4.17 source. Not verified: Windows process loopback and Linux parec on real machines, Firefox extension in a real call, captions/templates/e-mail against a real AI provider.

## Release v0.1.0 (proving it, merged to main)

- All phase PRs (#1-#11) merged into main; tagged v0.1.0. `TAURI_SIGNING_PRIVATE_KEY` is a repo secret; the release builds unsigned until the Apple secrets are added (it failed on empty Apple variables before, now fixed).
- Windows CI was hanging after 7 test failures, all in the tests (system-encoding text, `\\` paths, a test id too long for a Windows environment variable, a subprocess without `USERPROFILE`). Fixed; failures now reach the log (UTF-8, unbuffered, JUnit artifact).
- Real audio in CI ("Meeting-app audio" job): with a "zoom" and a "spotify" playing different tones, only zoom is recorded, on PulseAudio 16.1 (`engine/scripts/linux_app_audio_check.sh`) and on Windows WASAPI process loopback with a virtual sound card (`engine/scripts/windows_app_audio_check.py`).
- `engine/scripts/live_meeting_check.py`: real speech streamed into the live engine; the transcript, a fact check against an imported document ($50,000 vs $35,000), and notes. With an AI provider it also checks Turkish captions, Ask, the summary and the follow-up e-mail. Passed with Qwen2.5-3B (mlx-lm, local).
- Found by that run: small models close the JSON object early, which threw away every templated summary. `llm.json_object()` now serves the summary, the AI fact check and the hesitation pass.
- Desktop tests 46 → 83, line coverage 54% → 94% counting every source file; CI floor 90%.

## Pending

- Apple secrets (`APPLE_CERTIFICATE`, ...) for a signed, notarised app; then publish the v0.1.0 draft release.
- Real services not yet tried: Slack, Google Calendar, Gmail, Jira, Notion actions; a cloud AI provider (only a local model so far).
- A real multi-person call: speaker names and voice re-splitting.

## Known issues

- With "Hear only meeting apps" off, system capture transcribes any other audio playing. A browser's other tabs are kept out only with the browser extension (`RECALL_BROWSER_TAB_AUDIO`); Firefox and Safari have no tab-capture API for it.
- Open questions are tracked in `activeContext.md`.
