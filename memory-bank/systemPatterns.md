# System Patterns

## Data flow

```
system audio + mic -> audio (transcribe) -> diarization (who spoke)
                                                   |
human notes, docs, codebase ----------------> memory (SQLite + vector, tenant-scoped)
                                                   |
                                             LLM (Claude / Ollama)
                                              |             |
                                     hud (fact alerts)   actions (MCP tools, approval-gated)
```

## Repository layout

| Path | Responsibility |
| :--- | :--- |
| `apps/desktop/src-tauri/` | Rust shell: window, IPC commands, engine process lifecycle (`engine.rs`). No business logic. |
| `apps/desktop/src/` | React UI. `hud/` holds the transcript feed (main window) and the fact-check overlay (its own `hud` window). |
| `engine/src/continuum/audio/` | Loopback capture and transcription. |
| `engine/src/continuum/diarization/` | Speaker separation. |
| `engine/src/continuum/memory/` | Tenant-isolated vector memory (embedded Qdrant) and its search CLI. |
| `engine/src/continuum/factcheck/` | Figure extraction and the rule that flags statements contradicting memory. |
| `engine/src/continuum/actions/` | FastMCP server and external-system tools. |
| `engine/src/continuum/transport/` | Local WebSocket that streams transcript segments to the HUD. |
| `engine/src/continuum/pipeline.py` | Wires capture → chunk → transcribe → label → publish. No logic of its own. |
| `engine/src/continuum/transcript.py` | `Segment` and `Word`, the data shared by all engine modules. |

## Decisions

- **2026-10-11 — Greenfield, not a fork.** meetily, screenpipe, buzz, Anarlog, and whisperX are references or libraries, so the guidelines (SPDX headers, 800-line limit, no `unsafe`) hold from the first file.
- **2026-10-11 — Tauri 2 over Electron**, matching the Rust rules in `AI_GUIDELINES.md`.
- **2026-10-11 — One Python project, four packages.** Modules stay in separate packages (guideline §6) without the cost of several pyprojects. Split into separate projects only if dependency weight forces it.
- **2026-10-11 — MCP tool names are prefixed `continuum_`** so they stay unambiguous next to other servers.
- **2026-10-11 — Two channels between engine and desktop.** Live transcript goes over a local WebSocket (`ws://127.0.0.1:8765`, JSON `{"type": "segment", "segment": {...}}`); tool calls stay on FastMCP JSON-RPC. The WebSocket binds to loopback and rejects any `Origin` that is not the Tauri webview, so a web page in a browser cannot read transcripts.
- **2026-10-11 — System audio via ScreenCaptureKit from Python (PyObjC).** No virtual audio driver. Needs the macOS Screen Recording permission. macOS only for now.
- **2026-10-11 — faster-whisper directly, without whisperX.** faster-whisper already gives word timestamps and runs without torch; pyannote is called directly. Revisit whisperX only if word timing proves too loose.
- **2026-10-11 — Speaker labels in two tiers.** The audio source decides first (mic = `me`, system = `others`). With `HF_TOKEN` set, pyannote additionally separates speakers inside each system-audio utterance.
- **2026-10-11 — Utterance chunking by energy.** The stream is cut at 0.6 s pauses or at 15 s, then each utterance is transcribed. Latency is therefore one utterance, not word-by-word.
- **2026-10-11 — The desktop app runs the engine** (supersedes "started by hand"). On launch the Rust shell spawns `uv run continuum-engine` from `engine/` (or `CONTINUUM_ENGINE_DIR`) and stops it on exit. Shutdown signal is the engine's stdin closing: the app holds the pipe, so if the app exits or crashes the OS closes it and the engine stops recording. No signals, no `unsafe`. Release builds do not bundle the engine yet.
- **2026-10-11 — Memory isolation is enforced twice.** Each tenant/project pair has its own Qdrant collection (name = hash of both IDs), and every query also filters on tenant and project. The only read/write API is `MemoryStore.scoped(TenantScope)`; there is no unscoped call. With no tenant/project configured, nothing is stored.
- **2026-10-11 — Embedded Qdrant only, no SQLite yet.** Segment text, speaker, source, meeting and time live in the Qdrant payload. Add SQLite when something needs ordered or relational reads.
- **2026-10-11 — Local multilingual embeddings** (fastembed), so nothing leaves the machine and meetings need not be in English. Model is `paraphrase-multilingual-mpnet-base-v2` (768 dimensions, about 1 GB); it replaced MiniLM-L12, which could not separate related from unrelated statements. Collections are keyed by model as well as scope, so changing model starts fresh instead of mixing vectors.
- **2026-10-11 — One engine run is one meeting**, identified by a random ID and its start time.

- **2026-10-11 — Fact check v1 is a numbers rule, not an LLM.** For a live statement containing a figure (money, percent, counted unit), memory is searched with the figures masked out (topic only); among hits scoring ≥ 0.30 that mention the same kind of figure, the most recent is the record; no shared value means an alert. Statements are checked before they are stored, and a flagged statement is stored as `disputed` so it can never become the record. Threshold calibrated on 17 English/Turkish pairs (related 0.33–0.59, unrelated 0.03–0.23).
- **2026-10-11 — Alerts travel on the transcript WebSocket** as `{"type": "fact_check", "alert": {...}}`.
- **2026-10-11 — The HUD is a second Tauri window** (`hud`): transparent, undecorated, always on top, top-right. It is never hidden, because macOS suspends scripts in hidden windows and it would stop reconnecting; when empty it is one click-through pixel. Needs `macOSPrivateApi` for transparency. The app exits when the main window closes.
- **2026-10-11 — Tailwind CSS v4** (Vite plugin, CSS-first config in `src/styles.css`) for desktop styling.

## Rules every module follows

- Entrypoints (`main.rs`, `main.tsx`, `server.py:main`) stay thin.
- Memory reads and writes always filter by `tenant_id` and `project_id`.
- Tools that change external state require user approval before running.
