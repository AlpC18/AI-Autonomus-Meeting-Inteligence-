# Project Continuum

Open-source autonomous AI meeting intelligence: live fact-checking, approval-gated actions, and per-project memory, all local-first.

- Spec: [`ai_meeting_intelligence_spec-v2.md`](ai_meeting_intelligence_spec-v2.md)
- Contribution rules: [`AI_GUIDELINES.md`](AI_GUIDELINES.md)
- Project memory: [`memory-bank/`](memory-bank/)

## Layout

- `apps/desktop/` — Tauri 2 + React desktop app
- `engine/` — Python engine (audio, diarization, memory, MCP actions)
- `apps/browser-extension/` — Chrome/Edge/Brave/Arc extension that sends only the meeting tab's audio

## Run

```bash
cd apps/desktop && pnpm install && pnpm tauri dev
cd engine && uv sync --all-extras && uv run pytest
cd engine && cp .env.example .env   # settings; the desktop app starts the engine itself
```

Release app: `cd apps/desktop && pnpm bundle` builds `Continuum.app` with the engine inside; on first launch it installs its Python environment (needs internet once). Settings (and API keys, kept in the macOS Keychain) are set in the app.

Languages: the app, notes, hints and AI summaries are in English or Turkish (**Language** in Settings); speech is transcribed in whatever language people speak, and promises and doubts are noticed in both English and Turkish.

Shared slides: with **Fact-check shared slides** on (macOS), the meeting window is read every 10 s with on-device text recognition and its figures are checked against memory like speech. Only meeting windows are read: native meeting apps, and browser windows whose title names a meeting site.

Meeting platforms: Continuum listens to the call's audio, so it works with any platform without a bot joining the meeting. With **Hear only meeting apps** on (macOS), it hears Microsoft Teams, Slack huddles, Zoom, Google Meet, Webex, FaceTime, Discord, WhatsApp, Skype, Telegram, Signal, Viber, WeChat, LINE, Amazon Chime, GoTo Meeting, RingCentral, Jitsi, Element and Tuple, plus any site in a browser or added to the Dock from Safari; add others under **More meeting apps**. On Windows 10 (2004) or later the same setting hears only the meeting app's process (WASAPI process loopback; Teams, Zoom, Slack, browsers and more, or `.exe` names under **More meeting apps**), falling back to all system audio if Windows refuses. On Linux all system audio is heard, so every platform works. Auto-start notices any app that starts using the microphone.

Calls in a browser tab: macOS hands over audio per app, so every tab of the browser would be heard. Instead, load `apps/browser-extension` in `chrome://extensions` (Developer mode → Load unpacked), turn on **Calls in the browser from the extension** in Settings, and click the extension's button on the meeting tab (it shows ON). Only that tab is heard, and browsers are left out of system audio.

Engine commands (run with `uv run` in `engine/`):

- `continuum-transcribe FILE` / `--watch FOLDER` — transcribe recordings to Markdown, SRT, VTT or text; `--remember` adds them to memory, `--summarize` appends an AI summary.
- `continuum-import-docs PATH...` — add Markdown, text or PDF documents (or folders) to the project's memory, so fact checks and answers cite them; `--forget` removes them. PDFs need `uv sync --extra documents`. While the engine runs, use **Add documents…** in the app instead (the command needs the engine stopped).
- `continuum-check-connections` — signs in to every configured integration (GitHub, GitLab, Jira, Notion, Google, Hugging Face) and asks the AI provider for a one-word reply, so a wrong token shows up before a meeting. The Settings screen's **Test connections** button runs it.
- `continuum-diagnostics` — a report for bug reports: versions, settings without secret values, configuration problems and the end of the engine log (`~/.continuum/logs/engine.log`) with secrets and personal data removed. The Settings screen's **Copy diagnostics** button copies it.
- `continuum-summarize NOTES.md` — AI summary, decisions and action items with Groq, Gemini, OpenRouter, Mistral, Ollama, LM Studio, OpenAI or Claude; `--propose` queues them for approval.
- `continuum-library` — past meetings for the desktop viewer.
- `continuum-ask "question"` — answer from past meetings, with quotes (while the app is closed; in the app use "Ask your meetings").
- `continuum-check-config`, `continuum-detect-call` — used by the app's settings screen and auto-start.
- `continuum-memory-search`, `continuum-actions-review`, `continuum-actions` (MCP server).

MIT licensed.
