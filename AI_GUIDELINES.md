# AI Guidelines for Project Recall Development (AI Meeting & Workflow Agent)

> [!IMPORTANT]
> All AI assistants contributing to this repository MUST read and adhere to these guidelines before proposing or executing any code changes.

## 📌 Project Context & Core Architecture
This codebase implements an **Autonomous AI Meeting Intelligence Platform**. It leverages desktop audio capture, speaker diarization, local RAG memory, and autonomous action engines (Jira, GitHub, Slack, Notion, etc.).

**Core Components & Tech Stack:**
- **Desktop / UI Layer:** Tauri (Rust backend + React/TypeScript frontend) or Electron.
- **Audio & Diarization Engine:** Python (`faster-whisper`, `whisperX`, `pyannote.audio`).
- **Memory & RAG Layer:** Embedded Qdrant / ChromaDB & SQLite (`screenpipe` pattern).
- **Orchestration & Tools:** LangChain / FastMCP (Model Context Protocol) / Claude / Ollama.

---

## 1. Zero Unsafe Policy (Rust Components)
Memory safety is the highest priority in backend/desktop system integration components.
- **Rule**: Do NOT use `unsafe` blocks in Rust modules under any circumstances.
- **Rationale**: Safety and stability are critical when capturing desktop audio streams and interacting with system drivers. Use safe abstractions provided by official crates.

## 2. Mandatory Documentation (/// & JSDoc)
All new code must be self-documenting for humans, future AI contexts, and LLM agent prompts.
- **Rule**: Every new `pub mod`, `pub struct`, `pub enum`, `pub fn` (Rust) as well as public TypeScript interfaces/classes/functions MUST include detailed doc-comments (`///` or JSDoc).
- **Format**: Bilingual (English / Turkish) explanations are accepted, but technical clarity and context parameters are mandatory.

## 3. Persistent Knowledge Base & Memory Bank (.md)
To maintain architectural continuity across different development sessions:
- **Rule**: All new features, AI prompt templates, or pipeline updates MUST immediately be logged in `knowledge/history/engine_features.md`.
- **Rule**: All bug fixes, crash resolutions, audio loopback fixes, or API rate-limit patches MUST immediately be logged in `knowledge/history/bug_fixes.md`.
- **Rule**: Updating these `.md` files upon completing a change is a **MANDATORY REQUIREMENT**, not an option.
- **Rule**: Before starting work, the AI assistant MUST search and read relevant files in the `knowledge/` and `memory-bank/` directories to understand existing pipelines, system patterns, and resolved issues.

## 4. Modular Responsibility
The codebase follows a strict modular and event-driven architecture.
- **Rule**: Keep entrypoints (`main.rs`, `index.ts`, `app.py`) thin.
- **Rule**: Delegate responsibilities to isolated modules:
  - `audio/` (Loopback capture, Whisper transcription)
  - `diarization/` (Speaker separation)
  - `memory/` (Vector DB & RAG storage)
  - `actions/` (Jira, GitHub, Slack, Calendar API integrations)
  - `hud/` (Real-time fact-checking overlay)
- **Rule**: Do NOT create "God Objects" or monoliths that mix audio stream handling with LLM prompt execution.

## 5. Verification & Zero-Error Policy
- **Rule**: Always verify code compilation (`cargo check`, `npm run typecheck`, `pytest`) after structural modifications.
- **Rule**: Maintain 0 compilation errors and 0 warnings.
- **Rule**: Avoid mock placeholders in production paths. Always use real or structured fallback interfaces.

## 6. Strict File Boundary Enforcement
- **Rule**: Existing module boundaries are ABSOLUTE and MUST NOT be merged or collapsed without explicit instruction.
- **Rule**: Do NOT combine audio processing logic with API action dispatching.
- **Violation Condition**: Merging modules or centralizing decoupled logic into single files invalidates the solution.

## 7. Scope Isolation Rule
- **Rule**: AI assistants must ONLY modify explicitly requested files or target modules.
- **Rule**: Expanding scope beyond requested boundaries or applying unasked refactors is STRICTLY FORBIDDEN.
- **Example**: If asked to fix a bug in `whisperx_pipeline.py`, ONLY touch `whisperx_pipeline.py`. Do NOT alter `jira_action.py` or `hud_overlay.tsx`.

## 8. No Implicit Refactor Rule
- **Rule**: Code refactoring is allowed ONLY when explicitly instructed.
- **Rule**: AI must treat the existing codebase as a production system. Preserving operational stability is prioritized over subjective "code cleaning".

## 9. API Accuracy & Dependency Enforcement
- **Rule**: Always adhere strictly to the latest stable documentation of key libraries (`tauri`, `winit`/`egui` or `electron`, `faster-whisper`, `whisperX`, `qdrant-client`, `pyannote.audio`).
- **Rule**: Do NOT use deprecated methods or APIs.
- **Rule**: If a library upgrade requires breaking structural changes across multiple modules, obtain explicit user confirmation before applying.

## 10. Single Responsibility Per File (SRP) & File Size Limits
- **Rule**: Every single file must have ONE specific, clearly defined responsibility.
- **Rule**: Code files MUST NOT exceed **800 lines**. If a file approaches this limit, split it logically into helper modules.

## 11. Multi-Module Coordination Protocol
- **Rule**: When executing changes that span across multiple modules (e.g., passing real-time transcript from Python audio engine to Tauri backend and frontend HUD):
  1. Analyze all target modules.
  2. Propose a step-by-step plan.
  3. Wait for user confirmation before writing code.

## 12. Strict Multi-Tenant Context Isolation (Security & Privacy)
- **Rule**: The RAG and memory engines MUST enforce strict project/tenant isolation.
- **Rule**: Context queries from Client A's meeting must NEVER leak data from Client B's vector collections.
- **Rule**: Ensure local storage and LLM payloads strictly filter by active `project_id` / `tenant_id`.

## 13. AI Behavior Lock
- AI must NOT assume missing context or invent unmentioned APIs.
- AI must NOT take unprompted initiative outside the user's instructions.
- If uncertain about architectural intention: **ASK FIRST**.

## 14. Memory Bank Structure (MANDATORY)

The project maintains a persistent `memory-bank/` folder as long-term project memory for all AI assistants:

```txt
memory-bank/
  projectbrief.md      # Source of truth for scope, goals, and core requirements.
  productContext.md    # Product vision, problem solved, UX & HUD goals.
  activeContext.md     # Current focus, active decisions, recent developments.
  systemPatterns.md    # Architecture, audio pipeline, RAG design, MCP tool specifications.
  techContext.md       # Tech stack (Tauri, Rust, Python, WhisperX, Qdrant, FastMCP).
  progress.md          # Completed features, pending tasks, known issues.
```

- **Rule**: Before starting any task, the AI MUST read all files in `memory-bank/`.
- **Rule**: Upon task completion, the AI MUST update `activeContext.md` and `progress.md`.

## 15. Documentation Quality Score Rule (MANDATORY)
- **Rule**: All public interfaces, structs, classes, functions, and MCP tools MUST be documented with a quality score target of **8/10 or higher**.
- **Rule**: Comments must explain **purpose, side-effects, constraints, and error behaviors** (not just repeating the function name).

```txt
0-3/10 = Missing or useless comment.
4-7/10 = Basic explanation, missing edge cases or API constraints.
8-10/10 = Excellent: clear technical purpose, error conditions, and integration notes for AI/human developers.
```

## 16. Copyright and SPDX Header Rule (MANDATORY)
- **Rule**: Every source file (`.rs`, `.ts`, `.tsx`, `.py`, `.wgsl`) MUST start with the exact two-line header:
  ```rust
  // SPDX-License-Identifier: MIT
  // Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.
  ```
  *(For Python files, use `#` comment syntax instead of `//`)*
