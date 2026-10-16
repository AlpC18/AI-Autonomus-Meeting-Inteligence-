# Tech Context

## Stack

| Layer | Choice | Status |
| :--- | :--- | :--- |
| Desktop shell | Tauri 2, Rust 1.95 (edition 2024) | scaffolded |
| Frontend | React 19, TypeScript 6, Vite 8, pnpm 10 | scaffolded |
| Engine | Python 3.12 (pinned), uv | running |
| MCP | FastMCP 4.1 | health tool only |
| Transcription | faster-whisper (word timestamps, Silero VAD) | working |
| Audio capture | sounddevice (mic), ScreenCaptureKit via PyObjC (system, macOS) | working |
| Transport | websockets (transcript stream) | working |
| Diarization | pyannote.audio 4 (`speaker-diarization-community-1`), optional extra | integrated, not yet run with a real token |
| Vector DB | embedded Qdrant (qdrant-client local mode) + fastembed | working |
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
```

## Configuration

Environment variables, documented in `engine/.env.example`: `HF_TOKEN`, `CONTINUUM_SOURCES`, `CONTINUUM_WHISPER_MODEL`, `CONTINUUM_MODEL_DIR`, `CONTINUUM_WS_PORT`, `CONTINUUM_TENANT_ID`, `CONTINUUM_PROJECT_ID`, `CONTINUUM_MEMORY_DIR`. The desktop app reads `CONTINUUM_ENGINE_DIR` to locate the engine.

Heavy files can live off the system disk: point `UV_CACHE_DIR` and `CONTINUUM_MODEL_DIR` elsewhere and make `engine/.venv` a symlink.

## Known constraints

- System audio capture is macOS-only and needs Screen Recording permission for the app that runs the engine.
- pyannote speaker labels are only consistent within one utterance; stable identities across a meeting need speaker-embedding matching.
- Only one process can open the memory database at a time, so search from another process needs the engine stopped.
- Memory is stored unencrypted in `~/.continuum/memory` (folder readable by the user only).
- The engine is not bundled into release builds; the app needs `uv` on its PATH and the repo's `engine/` folder.
- The spec links Buzz as `chime-vc/buzz`; verify the correct upstream before using it.
