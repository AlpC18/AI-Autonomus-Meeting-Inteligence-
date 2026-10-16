# Active Context

_Last updated: 2026-10-12_

## Current focus

Stable speaker names and the GitHub issue action (Phase 5) are implemented on branch `feat/phase-5-github-action`, uncommitted, stacked on `feat/phase-4-fact-check-hud` (PR #2) which is stacked on `feat/phase-3-memory-sidecar` (PR #1). `main` holds Phases 1 and 2.

## What works end to end

- Live transcript, memory and fact-check overlay (Phases 2-4).
- With `HF_TOKEN` set, people heard through system audio are named "Speaker 1", "Speaker 2", ... and keep that name for the session. Verified with the real pyannote model on a public two-person recording.
- An assistant connected to the `continuum-actions` MCP server can propose a GitHub issue; the user sees it in the desktop app or the review CLI; approving creates it once.

## Waiting on the owner

- **Revoke the first Hugging Face token** that was shared and then withdrawn.
- **`engine/.env` still lacks** `CONTINUUM_TENANT_ID` + `CONTINUUM_PROJECT_ID` (memory and fact checking are off without them), `CONTINUUM_GITHUB_REPOS` and `GITHUB_TOKEN` (actions).
- **An LLM** (`ANTHROPIC_API_KEY` or Ollama) for action-item extraction and non-numeric fact checks.
- **Credentials** for Jira, Slack/Discord and Google Calendar.
- **Git name** in `~/.gitconfig` still has "Çığtekin"; this repo overrides it locally.

## Next up

- Speaker names in a real multi-person meeting (so far verified on a recording, not live capture); short utterances with two voices get one name.
- LLM extraction of action items feeding `ActionStore.propose`.
- Further action kinds through the same gate (Slack/Discord webhook, Jira, Calendar).

## Open questions

- System audio also captures unrelated media playing on the machine; limit capture to the meeting app?
- How the user picks tenant/project per meeting (today: environment variables).
- Bundling the engine for release builds.
- Windows and Linux system audio and overlay behaviour.
- `AI_GUIDELINES_v2026.md` and `AI_Guidelines_Architecture_Standards.md` are unfilled templates; remove or archive?

## Recent decisions

See `systemPatterns.md` → Decisions.
