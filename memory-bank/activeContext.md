# Active Context

_Last updated: 2026-10-11_

## Current focus

Phase 3 (memory and engine lifecycle) is implemented on branch `feat/phase-3-memory-sidecar`, uncommitted. `main` holds Phases 1 and 2 and is pushed to the private GitHub repo `AlpC18/AI-Autonomus-Meeting-Inteligence-`.

## What works end to end

Opening the desktop app starts the engine → audio is captured and transcribed → segments appear in the window and, when a tenant and project are configured, are stored in that scope's memory → closing (or crashing) the app stops the engine. Stored segments can be searched per scope with `continuum-memory-search`.

## Waiting on the owner

- **Hugging Face token.** `engine/.env` does not exist yet. Create it from `.env.example`, set `HF_TOKEN`, and accept the terms of `pyannote/speaker-diarization-community-1`. The real multi-speaker check has not been run.
- **Tenant and project.** Set `CONTINUUM_TENANT_ID` and `CONTINUUM_PROJECT_ID` in `engine/.env`, otherwise nothing is stored.
- **Git name.** `~/.gitconfig` still has "Çığtekin"; this repo overrides it locally with "Çiğtekin".

## Next up

- Run pyannote for real, then give speakers a stable identity across a meeting (match the pipeline's speaker embeddings per session).
- Fact-checking HUD: query memory from inside the engine for each new segment and push alerts over the WebSocket.

## Open questions

- How the user picks tenant/project per meeting (today: environment variables).
- Bundling the engine for release builds (today: `uv run` from the repo).
- Serving memory search to other processes while the engine runs (embedded Qdrant allows one process).
- Windows and Linux system audio capture.
- `AI_GUIDELINES_v2026.md` and `AI_Guidelines_Architecture_Standards.md` are unfilled templates; remove or archive?
- The spec's Buzz link (`chime-vc/buzz`) needs verifying.

## Recent decisions

See `systemPatterns.md` → Decisions.
