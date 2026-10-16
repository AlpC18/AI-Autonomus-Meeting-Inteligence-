# Engine Features

Log every new feature, AI prompt template, or pipeline update here (`AI_GUIDELINES.md` §3). Newest first.

| Date | Module | Feature | Notes |
| :--- | :--- | :--- | :--- |
| 2026-10-14 | desktop | Past meetings viewer | `continuum-library` + Rust commands; search, filter, click-to-play recordings, summarize button. |
| 2026-10-14 | transcribe | VTT, watch folder, import into memory | `--format vtt`, `--watch FOLDER`, `--remember` with content-hash meeting ids. |
| 2026-10-14 | privacy | Redaction and retention | Personal data and secrets hidden before memory/notes; `CONTINUUM_RETENTION_DAYS`; FileVault warning. |
| 2026-10-14 | hud | Live notepad and speaker renaming | Notes and renames sent over the transcript socket; notes become "Note" lines. |
| 2026-10-14 | audio | mlx-whisper backend | `CONTINUUM_ASR_BACKEND=auto` uses the Apple Silicon GPU; ~3.4x faster on M1. |
| 2026-10-14 | summary | AI summaries with any provider | `continuum-summarize`; prompt in `summary.SYSTEM_PROMPT`; free providers and Claude. |
| 2026-10-14 | actions | Jira issue action | `continuum_propose_jira_issue`; a Task in an allowed project on the configured Atlassian Cloud site after approval. |
| 2026-10-12 | desktop | Proposed-actions panel | Lists pending proposals in full with Approve and Reject; backed by Rust commands that run the review CLI. |
| 2026-10-12 | actions | `continuum-actions-review` CLI | list / approve / reject; approval asks for confirmation and refuses without a terminal unless `--yes`. |
| 2026-10-12 | actions | GitHub issue action with approval gate | Propose-only MCP tools, repo allowlist, tamper check, single-use approval, SQLite audit trail. |
| 2026-10-12 | hud | Per-speaker transcript lines | A segment with several voices is shown as one line per speaker turn. |
| 2026-10-12 | actions | Google Calendar deadline action | `continuum_propose_calendar_deadline`; all-day event on the configured calendar after approval. |
| 2026-10-12 | actions | Slack message action | `continuum_propose_slack_message`; posts to the one configured incoming webhook after approval. |
| 2026-10-12 | diarization | Stable speaker names across a session | `SpeakerTracker` matches voice embeddings to speakers already heard; system-audio speakers are "Speaker 1", "Speaker 2", ... |
| 2026-10-12 | pipeline | Engine starts without pyannote when the model cannot be loaded | Logs the reason, keeps source-based speaker labels. |
| 2026-10-11 | hud | Fact-check overlay window | Floating always-on-top card: said now vs on record, source quote, speaker and date; dismiss button, 30 s auto-dismiss, max 3 cards. |
| 2026-10-11 | transport | `fact_check` messages | Alerts are broadcast on the transcript WebSocket. |
| 2026-10-11 | pipeline | Live fact checking | Each segment is checked before it is stored; flagged segments are stored as disputed. |
| 2026-10-11 | factcheck | Figure extraction and contradiction rule | Money, percent and counted units (English and Turkish); topic search with figures masked; most recent undisputed record wins. |
| 2026-10-11 | memory | Model-keyed collections, `disputed` flag, mpnet default | Switching embedding model no longer mixes vectors. |
| 2026-10-11 | desktop | Engine lifecycle (`engine.rs`) | App spawns the engine on launch, stops it on exit; engine also stops if the app crashes (stdin pipe closes). |
| 2026-10-11 | pipeline | Memory ingestion and clean shutdown | Every published segment is stored when tenant and project are set; stops on SIGTERM or closed stdin. |
| 2026-10-11 | memory | `continuum-memory-search` CLI | Semantic search within the configured tenant and project only. |
| 2026-10-11 | memory | Tenant-isolated vector store | Embedded Qdrant, one collection per tenant/project plus payload filter; local multilingual embeddings. |
| 2026-10-11 | hud | Live transcript feed | `useTranscriptStream` hook (validates messages, auto-reconnects) and `TranscriptFeed` component. |
| 2026-10-11 | pipeline | `continuum-engine` console script | Captures the configured sources, transcribes, labels speakers, publishes. One failing source does not stop the others. |
| 2026-10-11 | transport | Transcript WebSocket server | Loopback only, Origin allowlist, JSON segment messages. |
| 2026-10-11 | diarization | Speaker labelling | Source-based labels always; pyannote turns mapped onto words by overlap when `HF_TOKEN` is set. |
| 2026-10-11 | audio | Transcription | faster-whisper with word timestamps; times on a shared stream timeline. |
| 2026-10-11 | audio | Utterance chunker | Splits streams at pauses (0.6 s) or 15 s; drops sub-0.3 s blips. |
| 2026-10-11 | audio | Microphone and system audio capture | 16 kHz mono float32 blocks; system audio through ScreenCaptureKit, no driver. |
| 2026-10-11 | actions | `continuum_health` MCP tool and `continuum-actions` stdio server | Read-only; returns status and engine version. Tested through FastMCP's in-memory client. |
| 2026-10-11 | desktop | `app_info` Tauri command and shell window | Returns crate name and version; proves the webview-to-Rust IPC path. |
| 2026-10-11 | all | Repository scaffold | Module packages created for audio, diarization, memory, actions, hud; all but actions are empty until later phases. |
