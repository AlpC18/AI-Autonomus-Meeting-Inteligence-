# Project Brief

**Project Recall** is an open-source, autonomous AI meeting intelligence platform. Full spec: `ai_meeting_intelligence_spec-v2.md`. Rules: `AI_GUIDELINES.md`.

## Goal

Go beyond passive transcription tools (Fireflies, Otter): act during and after meetings instead of only summarising them.

## Core requirements

1. Botless desktop audio capture (system audio and microphone as separate streams).
2. Word-level transcription with speaker diarization.
3. Persistent local memory (SQLite + vector DB) over meetings, notes, documents, and code.
4. Real-time fact-checking HUD that flags conflicts with past decisions.
5. Autonomous action engine (Jira, GitHub, Slack, Notion, Calendar) that executes only after user approval.
6. Codebase and architecture context mapping for technical discussions.
7. Risk and commitment tracking (over-promising, hesitation markers).
8. Strict per-tenant, per-project isolation of all stored and retrieved data.

## Out of scope for now

Cloud hosting, meeting bots that join calls, mobile apps.
