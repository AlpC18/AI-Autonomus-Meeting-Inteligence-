# Active Context

_Last updated: 2026-10-17_

## Current focus

All phase PRs (#1-#12) are merged into `main` and tagged v0.1.0 (macOS arm64 build, draft release, unsigned until the Apple secrets exist). Phase 13 (`feat/phase-13-suggestions`): spoken Turkish numbers in fact checks, housekeeping, and these notes brought up to date.

## What works end to end

- Live transcript, memory and fact-check overlay (Phases 2-4).
- With `HF_TOKEN` set, people heard through system audio are named "Speaker 1", "Speaker 2", ... and keep that name for the session. Verified with the real pyannote model on a public two-person recording.
- The transcript shows one line per speaker turn, so a segment with several voices is split by who spoke.
- Slack messages, Google Calendar deadlines and Jira Tasks can be proposed and approved like GitHub issues. Only unit-tested against fake servers: no Slack webhook, Google or Jira credentials exist on this machine.
- Live run on 2026-10-12 through the desktop app: system audio captured, four voices named, statements stored in memory under a test tenant and invisible to another tenant, the $50,000 vs $35,000 contradiction flagged, a Slack proposal queued through the MCP tool and shown in the panel.
- An assistant connected to the `recall-actions` MCP server can propose a GitHub issue; the user sees it in the desktop app or the review CLI; approving creates it once.
- Verified live on 2026-10-14: notes and speaker renames over the engine socket (other origins refused, oversized notes ignored); `--watch` transcribing a dropped recording; `recall-library` list/search/show and folder confinement; mlx backend on the M1 (0.38 s vs 1.29 s per 8 s utterance for "base").
- Not verified live: AI summaries, answers and AI fact checks (no provider key or running local model on this machine); the viewer's audio playback inside the Tauri window; Windows/Linux loopback on real hardware.
- Verified live on 2026-10-15: release `Recall.app` installed managed Python 3.12 + the locked environment and the window connected to its engine; Keychain round trip; call detection (mic used by another stream → true, released → false; watcher exits with the app); end_meeting/ask/note over the real engine socket with recording.

## Waiting on the owner

- **Apple signing secrets** (`APPLE_CERTIFICATE`, ...) for a signed, notarised app; then publish the v0.1.0 draft release. Back up `~/.tauri/continuum-updater.key`: losing it means installed apps can't update.

- **Revoke the first Hugging Face token** that was shared and then withdrawn.
- **`engine/.env` still lacks** `RECALL_TENANT_ID` + `RECALL_PROJECT_ID` (memory and fact checking are off without them), `RECALL_GITHUB_REPOS` and `GITHUB_TOKEN`, `RECALL_SLACK_WEBHOOK_URL`, the three `GOOGLE_*` values, and `RECALL_JIRA_SITE` + `JIRA_EMAIL` + `JIRA_API_TOKEN` + `RECALL_JIRA_PROJECTS` (actions).
- **An LLM** for summaries: set `RECALL_LLM_PROVIDER` (free: groq, gemini, openrouter, mistral; local: ollama, lmstudio; or anthropic) and its key. Also needed for non-numeric fact checks.
- **`uv sync --extra apple`** for the faster mlx speech backend (a plain `uv sync` removes it).
- **Git name** in `~/.gitconfig` still has "Çığtekin"; this repo overrides it locally.

## Next up

- Speaker names in a real multi-person call (so far verified on a recording, not live capture); short utterances with two voices get one name.
- Run a summary against a cloud provider (only a local model so far).
- Tag v0.2.0 to get the first four-platform release (Windows and Linux builds have only been compiled in CI, not installed on real hardware).

Already done (older notes listed them as open): in-app Google consent (Settings → Connect Google), live recording with playback in the Library (`RECALL_RECORD_AUDIO`), picking or switching the project from the app (Settings and the meeting bar), the engine bundled in release builds (verified 2026-10-17: the v0.1.0 app installs its locked environment from a clean state and imports the engine), and a summary when a meeting ends.

## Open questions

- Encrypt memory at the application level? Not done: notes, recordings and voices are plain files by design, so encrypting only the vector store would add little. The "only store on an encrypted disk" setting covers it.

## Recent decisions

See `systemPatterns.md` → Decisions.
