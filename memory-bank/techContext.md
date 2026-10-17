# Tech Context

## Stack

| Layer | Choice | Status |
| :--- | :--- | :--- |
| Desktop shell | Tauri 2, Rust 1.95 (edition 2024) | scaffolded |
| Frontend | React 19, TypeScript 6, Vite 8, Tailwind CSS 4, pnpm 10 | transcript feed + fact-check overlay |
| Engine | Python 3.12 (pinned), uv | running |
| MCP | FastMCP 4.1 | health, propose GitHub issue, list pending |
| Actions | SQLite queue + httpx; GitHub issues | working, verified against GitHub |
| Transcription | faster-whisper (word timestamps, Silero VAD) | working |
| Audio capture | sounddevice (mic), ScreenCaptureKit via PyObjC (system, macOS) | working |
| Transport | websockets (transcript stream) | working |
| Diarization | pyannote.audio 4 (`speaker-diarization-community-1`), optional extra | run with the real model since 2026-10-12 |
| Vector DB | embedded Qdrant (qdrant-client local mode) + fastembed (multilingual mpnet, ~1 GB) | working |
| Fact check | numbers rule over memory hits (no LLM) | working |
| Relational store | SQLite | not needed yet |
| Engine lifecycle | spawned and stopped by the Tauri shell | working (dev builds) |
| LLM | Claude / Ollama | later |

## Commands

```bash
# desktop
cd apps/desktop && pnpm install
pnpm typecheck
pnpm tauri dev
cd src-tauri && cargo check && cargo clippy -- -D warnings

# engine
cd engine && uv sync --all-extras          # --all-extras adds pyannote + torch
uv run pytest                             # downloads Whisper "tiny" once
cp .env.example .env                      # then fill in HF_TOKEN etc.
uv run --env-file .env continuum-engine   # run the engine alone (the desktop app normally starts it)
uv run --env-file .env continuum-memory-search "what was the budget"   # engine must be stopped
uv run continuum-actions                  # MCP server over stdio
uv run --env-file .env continuum-actions-review list            # or: approve ID / reject ID
```

## Configuration

Environment variables, documented in `engine/.env.example`: `HF_TOKEN`, `CONTINUUM_SOURCES`, `CONTINUUM_WHISPER_MODEL`, `CONTINUUM_MODEL_DIR`, `CONTINUUM_WS_PORT`, `CONTINUUM_TENANT_ID`, `CONTINUUM_PROJECT_ID`, `CONTINUUM_MEMORY_DIR`, `CONTINUUM_GITHUB_REPOS`, `GITHUB_TOKEN`, `CONTINUUM_ACTIONS_DB`. The desktop app reads `CONTINUUM_ENGINE_DIR` to locate the engine.

Heavy files can live off the system disk: point `UV_CACHE_DIR` and `CONTINUUM_MODEL_DIR` elsewhere and make `engine/.venv` a symlink.

## Known constraints

- System audio: macOS uses ScreenCaptureKit and needs Screen Recording permission for the app that runs the engine; Windows uses WASAPI (process) loopback; Linux uses PulseAudio/PipeWire (`pactl`, `parec` from pulseaudio-utils).
- pyannote labels are only valid inside one call. Session-wide names come from matching voice embeddings (`diarization/tracker.py`); embed each speaker's own audio, because the embeddings the pipeline returns for short clips are mixtures and do not match across calls.
- pyannote costs about 0.9 s of CPU per second of audio beyond the first 10 s on an M1 (the wespeaker embedding model dominates; MPS and a coarser segmentation step did not help).
- `uv run --env-file` silently drops a value with unquoted spaces; quote such paths in `engine/.env`.
- Fact checking compares figures with a known unit or currency (digits, spelled-out English and Turkish numbers, dates with a month name). Contradictions without numbers need the opt-in AI check (`factcheck/semantic.py`) and a configured provider. Turkish number words with suffixes ("dolarlık") are not read.
- System audio captures everything the machine plays, so unrelated media is transcribed and stored too.
- Only one process can open the memory database at a time, so search from another process needs the engine stopped.
- Memory is stored unencrypted in `~/.continuum/memory` (folder readable by the user only).
- The engine is not bundled into release builds; the app needs `uv` on its PATH and the repo's `engine/` folder.
- The spec links Buzz as `chime-vc/buzz`; verify the correct upstream before using it.
