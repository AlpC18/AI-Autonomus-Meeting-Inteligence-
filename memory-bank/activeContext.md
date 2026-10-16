# Active Context

_Last updated: 2026-10-11_

## Current focus

Fact-check HUD (first part of Phase 4) is implemented on branch `feat/phase-4-fact-check-hud`, uncommitted, stacked on `feat/phase-3-memory-sidecar` (PR #1, open). `main` holds Phases 1 and 2.

## What works end to end

Open the app → engine starts → speech is transcribed → each statement with a figure is compared with the project's memory → a contradiction shows as a floating card at the top-right of the screen → the statement is stored (as disputed if it was flagged).

## Waiting on the owner

- **`engine/.env` does not exist.** It needs `HF_TOKEN` (pyannote, speaker clustering) and `CONTINUUM_TENANT_ID` + `CONTINUUM_PROJECT_ID` (without them nothing is stored and nothing is fact-checked).
- **An LLM** (`ANTHROPIC_API_KEY` or Ollama) for non-numeric contradictions and for extracting action items.
- **Credentials** for Jira, Slack and Google Calendar before those action tools can be tested for real. GitHub is reachable through `gh`.
- **Git name** in `~/.gitconfig` still has "Çığtekin"; this repo overrides it locally.

## Next up

- Speaker clustering once the token exists.
- Approval-gated action tools, starting with GitHub issues (`mcp-builder`, `securing-agentic-ai-tool-invocation`).

## Open questions

- System audio also captures unrelated media playing on the machine; should capture be limited to the meeting app?
- How the user picks tenant/project per meeting (today: environment variables).
- Bundling the engine for release builds.
- Windows and Linux system audio and overlay behaviour.
- `AI_GUIDELINES_v2026.md` and `AI_Guidelines_Architecture_Standards.md` are unfilled templates; remove or archive?

## Recent decisions

See `systemPatterns.md` → Decisions.
