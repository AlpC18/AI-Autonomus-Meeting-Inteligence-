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
uv run --env-file .env recall-engine   # run the engine alone (the desktop app normally starts it)
uv run --env-file .env recall-memory-search "what was the budget"   # engine must be stopped
uv run recall-actions                  # MCP server over stdio
uv run --env-file .env recall-actions-review list            # or: approve ID / reject ID
```

## Configuration

Environment variables, documented in `engine/.env.example`: `HF_TOKEN`, `RECALL_SOURCES`, `RECALL_WHISPER_MODEL`, `RECALL_MODEL_DIR`, `RECALL_WS_PORT`, `RECALL_TENANT_ID`, `RECALL_PROJECT_ID`, `RECALL_MEMORY_DIR`, `RECALL_GITHUB_REPOS`, `GITHUB_TOKEN`, `RECALL_ACTIONS_DB`. The desktop app reads `RECALL_ENGINE_DIR` to locate the engine.

Heavy files can live off the system disk: point `UV_CACHE_DIR` and `RECALL_MODEL_DIR` elsewhere and make `engine/.venv` a symlink.

## Known constraints

- System audio: macOS uses ScreenCaptureKit and needs Screen Recording permission for the app that runs the engine; Windows uses WASAPI (process) loopback; Linux uses PulseAudio/PipeWire (`pactl`, `parec` from pulseaudio-utils).
- pyannote labels are only valid inside one call. Session-wide names come from matching voice embeddings (`diarization/tracker.py`); embed each speaker's own audio, because the embeddings the pipeline returns for short clips are mixtures and do not match across calls.
- pyannote costs about 0.9 s of CPU per second of audio beyond the first 10 s on an M1 (the wespeaker embedding model dominates; MPS and a coarser segmentation step did not help).
- `uv run --env-file` silently drops a value with unquoted spaces; quote such paths in `engine/.env`.
- Fact checking compares figures with a known unit or currency in English, Turkish, German and Italian: digits, spelled-out numbers (German and Italian one-word compounds in `factcheck/compound_numbers.py`), "Millionen"/"mila"-style scale words, percent words and dates with a month name. German and Italian units map to the English unit, so figures compare across languages; Turkish units keep their own names. Turkish units are read with common case and "-lık" endings. Contradictions without numbers need the opt-in AI check (`factcheck/semantic.py`). Other languages: only digits with a currency symbol or `%`.
- System audio captures everything the machine plays, so unrelated media is transcribed and stored too.
- Only one process can open the memory database at a time, so search from another process needs the engine stopped.
- Memory is stored unencrypted in `~/.recall/memory` (folder readable by the user only).
- Release builds bundle the engine sources, `uv.lock` and a `uv` binary (`tauri.bundle.conf.json`); the first start installs Python 3.12 and the locked environment into the app's data folder, which needs an internet connection once. Dev builds use `uv` from the PATH and the repo's `engine/` folder.
- Release platforms: macOS 14+ arm64 and x86_64, Windows x86_64, Linux x86_64. `[tool.uv] required-environments` keeps the lock installable on each, and `engine/scripts/check_release_wheels.sh` (CI) fails if any package would need building from source. macOS 14 is the floor because `av` and `onnxruntime` ship arm64 wheels for 14+ only. Intel Macs get onnxruntime 1.23.2 and cryptography <49 (last with Intel wheels) and no speaker names (no PyTorch).
- Installer check: on pull requests that touch packaging, `release.yml` builds all four platforms without publishing, installs each (`.app`, `.deb` via apt, NSIS `/S`), and `apps/desktop/scripts/smoke-bundle.mjs` starts the installed engine the way the app does. The app binary is `recall` and the bundled uv is `recall-uv` (so the Linux package never claims `/usr/bin/uv`).
- Bundled extras: `claude` and `documents` always, `apple` on Apple Silicon, `diarization` once `HF_TOKEN` is set (`engine.rs`, `Bundle::extras`).
- The spec links Buzz as `chime-vc/buzz`; verify the correct upstream before using it.
- Speech accuracy measured 2026-10-17 on Turkish, German and Italian (macOS voices): base garbles words, small mostly right (~1 s per sentence on M1), large-v3-turbo word-perfect. The after-meeting redo of a 45 s three-language meeting took ~60 s, mostly loading the model.
- Albanian (tested 2026-10-17 with Microsoft neural voices via edge-tts): live "small" is unusable, medium switches to Cyrillic, large-v3 is no better than large-v3-turbo; turbo with the meeting-language list gets most words right, some misspelled ("Bugjeti uull"). The fact checker reads Albanian digits/units/currency (lek), spoken numbers ("tridhjetë e pesë mijë"), "për qind" and month names.
