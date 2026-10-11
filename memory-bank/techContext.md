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
| Vector DB | embedded Qdrant | Phase 3 |
| Relational store | SQLite | Phase 3 |
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
uv run --env-file .env continuum-engine   # live capture + transcript WebSocket
uv run continuum-actions                  # MCP server over stdio
```

## Configuration

Environment variables, documented in `engine/.env.example`: `HF_TOKEN`, `CONTINUUM_SOURCES`, `CONTINUUM_WHISPER_MODEL`, `CONTINUUM_MODEL_DIR`, `CONTINUUM_WS_PORT`.

Heavy files can live off the system disk: point `UV_CACHE_DIR` and `CONTINUUM_MODEL_DIR` elsewhere and make `engine/.venv` a symlink.

## Known constraints

- System audio capture is macOS-only and needs Screen Recording permission for the app that runs the engine.
- pyannote speaker labels are only consistent within one utterance; stable identities across a meeting need speaker-embedding matching.
- The spec links Buzz as `chime-vc/buzz`; verify the correct upstream before using it.
