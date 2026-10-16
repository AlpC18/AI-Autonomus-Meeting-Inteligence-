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

## Pending

- **Real pyannote run** once `HF_TOKEN` is in `engine/.env`; then stable speaker identity across utterances.
- **HUD phase:** fact-checking overlay and notepad UI.
- **Actions phase:** Jira/GitHub/Slack/Calendar MCP tools with approval gate; security review.
- Bundling the engine into release builds; choosing tenant/project from the UI; non-macOS system audio.
- CI workflow and pre-commit checks (add when there is logic to guard).

## Known issues

- While other audio is playing on the machine, system capture transcribes that too, and utterances can be cut at the 15 s limit mid-sentence.
- Open questions are tracked in `activeContext.md`.
