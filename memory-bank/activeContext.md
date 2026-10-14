# Active Context

_Last updated: 2026-10-12_

## Current focus

Phase 6 (integration) is in progress on branch `feat/phase-6-integration`, uncommitted: per-speaker transcript lines, Slack and Google Calendar connectors, and a live end-to-end run. Phase 5 is committed and open as PR #4, stacked on PR #2 (`feat/phase-4-fact-check-hud`), which is stacked on PR #1 (`feat/phase-3-memory-sidecar`). `main` holds Phases 1 and 2.

## What works end to end

- Live transcript, memory and fact-check overlay (Phases 2-4).
- With `HF_TOKEN` set, people heard through system audio are named "Speaker 1", "Speaker 2", ... and keep that name for the session. Verified with the real pyannote model on a public two-person recording.
- The transcript shows one line per speaker turn, so a segment with several voices is split by who spoke.
- Slack messages and Google Calendar deadlines can be proposed and approved like GitHub issues. Only unit-tested against fake servers: no Slack webhook or Google credentials exist on this machine.
- Live run on 2026-10-12 through the desktop app: system audio captured, four voices named, statements stored in memory under a test tenant and invisible to another tenant, the $50,000 vs $35,000 contradiction flagged, a Slack proposal queued through the MCP tool and shown in the panel.
- An assistant connected to the `continuum-actions` MCP server can propose a GitHub issue; the user sees it in the desktop app or the review CLI; approving creates it once.

## Waiting on the owner

- **Revoke the first Hugging Face token** that was shared and then withdrawn.
- **`engine/.env` still lacks** `CONTINUUM_TENANT_ID` + `CONTINUUM_PROJECT_ID` (memory and fact checking are off without them), `CONTINUUM_GITHUB_REPOS` and `GITHUB_TOKEN`, `CONTINUUM_SLACK_WEBHOOK_URL`, and the three `GOOGLE_*` values (actions).
- **An LLM** (`ANTHROPIC_API_KEY` or Ollama) for action-item extraction and non-numeric fact checks.
- **Jira** connector is not built (deferred by the user on 2026-10-12); it needs a site URL, account email and API token.
- **Git name** in `~/.gitconfig` still has "Çığtekin"; this repo overrides it locally.

## Next up

- Speaker names in a real multi-person meeting (so far verified on a recording, not live capture); short utterances with two voices get one name.
- LLM extraction of action items feeding `ActionStore.propose`.
- Nothing turns what was said into a proposal yet: proposals come only from an assistant calling the MCP tools. Automatic extraction needs an LLM.
- Jira through the same gate; an in-app Google consent flow.

## Open questions

- System audio also captures unrelated media playing on the machine; limit capture to the meeting app?
- How the user picks tenant/project per meeting (today: environment variables).
- Bundling the engine for release builds.
- Windows and Linux system audio and overlay behaviour.
- `AI_GUIDELINES_v2026.md` and `AI_Guidelines_Architecture_Standards.md` are unfilled templates; remove or archive?

## Recent decisions

See `systemPatterns.md` → Decisions.
