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

MIT licensed.
