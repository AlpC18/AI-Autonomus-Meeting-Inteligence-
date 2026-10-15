# Active Context

_Last updated: 2026-10-15_

## Current focus

Phase 6 (integration) is on branch `feat/phase-6-integration`, open as PR #5 stacked on PR #4: per-speaker transcript lines, Slack, Google Calendar and Jira connectors, notes export, and a live end-to-end run. On 2026-10-14 eight features modelled on Meetily, Buzz, Screenpipe and Anarlog were added on branch `feat/phase-7-competitor-features` (PR #6, stacked on #5): AI summaries with any provider, mlx speech backend, live notepad, speaker renaming, redaction + retention, VTT + watch folder, recording import into memory, and the past-meetings viewer. Phase 5 is PR #4, stacked on PR #2 (`feat/phase-4-fact-check-hud`), which is stacked on PR #1 (`feat/phase-3-memory-sidecar`). `main` holds Phases 1 and 2.

Phase 8 (product completion) is on `feat/phase-8-product`, PR #7 stacked on #6: CI, in-app settings with Keychain secrets, packaged release app, meeting lifecycle (end meeting → summary, proposals, next meeting; idle end), ask your meetings, AI fact check, recording, duplicate-speaker merge, calendar titles, auto-start on calls, Windows/Linux loopback.

## What works end to end

- Live transcript, memory and fact-check overlay (Phases 2-4).
- With `HF_TOKEN` set, people heard through system audio are named "Speaker 1", "Speaker 2", ... and keep that name for the session. Verified with the real pyannote model on a public two-person recording.
- The transcript shows one line per speaker turn, so a segment with several voices is split by who spoke.
- Slack messages, Google Calendar deadlines and Jira Tasks can be proposed and approved like GitHub issues. Only unit-tested against fake servers: no Slack webhook, Google or Jira credentials exist on this machine.
- Live run on 2026-10-12 through the desktop app: system audio captured, four voices named, statements stored in memory under a test tenant and invisible to another tenant, the $50,000 vs $35,000 contradiction flagged, a Slack proposal queued through the MCP tool and shown in the panel.
- An assistant connected to the `continuum-actions` MCP server can propose a GitHub issue; the user sees it in the desktop app or the review CLI; approving creates it once.
- Verified live on 2026-10-14: notes and speaker renames over the engine socket (other origins refused, oversized notes ignored); `--watch` transcribing a dropped recording; `continuum-library` list/search/show and folder confinement; mlx backend on the M1 (0.38 s vs 1.29 s per 8 s utterance for "base").
- Not verified live: AI summaries, answers and AI fact checks (no provider key or running local model on this machine); the viewer's audio playback inside the Tauri window; Windows/Linux loopback on real hardware.
- Verified live on 2026-10-15: release `Continuum.app` installed managed Python 3.12 + the locked environment and the window connected to its engine; Keychain round trip; call detection (mic used by another stream → true, released → false; watcher exits with the app); end_meeting/ask/note over the real engine socket with recording.

## Waiting on the owner

- **Revoke the first Hugging Face token** that was shared and then withdrawn.
- **`engine/.env` still lacks** `CONTINUUM_TENANT_ID` + `CONTINUUM_PROJECT_ID` (memory and fact checking are off without them), `CONTINUUM_GITHUB_REPOS` and `GITHUB_TOKEN`, `CONTINUUM_SLACK_WEBHOOK_URL`, the three `GOOGLE_*` values, and `CONTINUUM_JIRA_SITE` + `JIRA_EMAIL` + `JIRA_API_TOKEN` + `CONTINUUM_JIRA_PROJECTS` (actions).
- **An LLM** for summaries: set `CONTINUUM_LLM_PROVIDER` (free: groq, gemini, openrouter, mistral; local: ollama, lmstudio; or anthropic) and its key. Also needed for non-numeric fact checks.
- **`uv sync --extra apple`** for the faster mlx speech backend (a plain `uv sync` removes it).
- **Git name** in `~/.gitconfig` still has "Çığtekin"; this repo overrides it locally.

## Next up

- Speaker names in a real multi-person meeting (so far verified on a recording, not live capture); short utterances with two voices get one name.
- Run a summary against a real provider; consider an automatic summary when a meeting ends.
- Optional recording of live meetings for playback (off by design today; only imported recordings play).
- An in-app Google consent flow.

## Open questions

- System audio also captures unrelated media playing on the machine; limit capture to the meeting app?
- How the user picks tenant/project per meeting (today: environment variables).
- Bundling the engine for release builds.
- Windows and Linux system audio and overlay behaviour.
- `AI_GUIDELINES_v2026.md` and `AI_Guidelines_Architecture_Standards.md` are unfilled templates; remove or archive?

## Recent decisions

See `systemPatterns.md` → Decisions.
