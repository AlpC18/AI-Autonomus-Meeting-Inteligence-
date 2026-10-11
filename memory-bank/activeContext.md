# Active Context

_Last updated: 2026-10-11_

## Current focus

Phase 2 (audio pipeline and real-time transport) is implemented and verified live on macOS. Nothing is in progress.

## What works end to end

System audio or microphone → utterance chunker → faster-whisper → speaker label → WebSocket → transcript list in the desktop window. Verified by playing a spoken sentence through the speakers and reading it in the app.

## Waiting on the owner

- **Hugging Face token.** Put `HF_TOKEN` in `engine/.env` and accept the terms of `pyannote/speaker-diarization-community-1`. Until then the pyannote path has only been tested against pyannote's data types, never against the real model.

## Next up

- Memory phase: Qdrant + SQLite store with tenant/project scoping (`agentdb-memory-patterns`), persisting the segments the engine already produces.
- Then the fact-checking HUD on top of memory.

## Open questions

- Stable speaker identity across a whole meeting (pyannote labels reset per utterance).
- Whether the desktop app should launch the engine itself (Tauri sidecar) instead of the user starting it.
- Windows and Linux system audio capture; only macOS is implemented.
- `AI_GUIDELINES_v2026.md` and `AI_Guidelines_Architecture_Standards.md` are unfilled templates that differ from `AI_GUIDELINES.md`; the owner may want to remove or archive them.
- The spec's Buzz link (`chime-vc/buzz`) needs verifying.

## Recent decisions

See `systemPatterns.md` → Decisions.
