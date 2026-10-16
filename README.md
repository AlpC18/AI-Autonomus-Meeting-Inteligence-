# Project Continuum

Open-source autonomous AI meeting intelligence: live fact-checking, approval-gated actions, and per-project memory, all local-first.

- Spec: [`ai_meeting_intelligence_spec-v2.md`](ai_meeting_intelligence_spec-v2.md)
- Contribution rules: [`AI_GUIDELINES.md`](AI_GUIDELINES.md)
- Project memory: [`memory-bank/`](memory-bank/)

## Layout

- `apps/desktop/` — Tauri 2 + React desktop app
- `engine/` — Python engine (audio, diarization, memory, MCP actions)

## Run

```bash
cd apps/desktop && pnpm install && pnpm tauri dev
cd engine && uv sync --all-extras && uv run pytest
cd engine && cp .env.example .env   # settings; the desktop app starts the engine itself
```

Release app: `cd apps/desktop && pnpm bundle` builds `Continuum.app` with the engine inside; on first launch it installs its Python environment (needs internet once). Settings (and API keys, kept in the macOS Keychain) are set in the app.

Engine commands (run with `uv run` in `engine/`):

- `continuum-transcribe FILE` / `--watch FOLDER` — transcribe recordings to Markdown, SRT, VTT or text; `--remember` adds them to memory.
- `continuum-summarize NOTES.md` — AI summary, decisions and action items with Groq, Gemini, OpenRouter, Mistral, Ollama, LM Studio, OpenAI or Claude; `--propose` queues them for approval.
- `continuum-library` — past meetings for the desktop viewer.
- `continuum-ask "question"` — answer from past meetings, with quotes (while the app is closed; in the app use "Ask your meetings").
- `continuum-check-config`, `continuum-detect-call` — used by the app's settings screen and auto-start.
- `continuum-memory-search`, `continuum-actions-review`, `continuum-actions` (MCP server).

MIT licensed.
