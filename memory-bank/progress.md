# Progress

## Done

### Phase 1 — Scaffold + memory bank (2026-10-11)

- Git repository initialised (no commits yet), MIT `LICENSE`, root `.gitignore`, `README.md`.
- `apps/desktop`: Tauri 2 + React/TS shell. One Rust command (`app_info`) displayed by the window. `hud/` module placeholder.
- `engine`: Python project with `audio`, `diarization`, `memory`, `actions` packages. FastMCP server with one tool (`continuum_health`) and a `continuum-actions` console script.
- `memory-bank/` (6 files) and `knowledge/history/` (2 logs) created.
- Verified: `cargo check` and `cargo clippy -- -D warnings` clean, `pnpm typecheck` clean, `uv run pytest` 1 passed, `pnpm tauri dev` window shows `desktop v0.1.0`, no `unsafe`, SPDX header on every source file.

### Phase 2 — Audio pipeline and real-time transport (2026-10-11)

- Alignment: author name corrected to "Yüksel Alp Çiğtekin" in `engine/pyproject.toml`; engine pinned to Python 3.12.
- `audio`: microphone capture (sounddevice), system audio capture (ScreenCaptureKit), utterance chunker, faster-whisper transcriber with word timestamps.
- `diarization`: source-based speaker labels; pyannote adapter and word-to-turn assignment.
- `transport`: loopback WebSocket server with Origin allowlist.
- `pipeline`: `continuum-engine` entry point; settings from environment (`engine/.env.example`).
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

## Pending

- **Speaker names:** check in a real meeting; separate two voices inside short utterances; let the user rename "Speaker 1".
- **HUD:** LLM judge for non-numeric contradictions; spelled-out numbers and dates; notepad UI.
- **Actions phase:** Jira/GitHub/Slack/Calendar MCP tools with approval gate; security review.
- Bundling the engine into release builds; choosing tenant/project from the UI; non-macOS system audio.
- CI workflow and pre-commit checks (add when there is logic to guard).

## Known issues

- While other audio is playing on the machine, system capture transcribes that too, and utterances can be cut at the 15 s limit mid-sentence.
- Open questions are tracked in `activeContext.md`.
