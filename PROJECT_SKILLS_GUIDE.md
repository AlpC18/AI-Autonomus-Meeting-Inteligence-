# Project Skill Integration & Execution Guide (Project Recall)

> **Document Purpose:** This document defines the exact skills required from the **Skill Direction Guide (Skill Yönlendirme Rehberi)** to build, test, secure, and scale our **Autonomous AI Meeting Intelligence Platform**. All AI agents contributing to this codebase must invoke the designated skills according to their domain responsibility.

---

## 📌 Executive Summary

Building an **Autonomous AI Meeting Intelligence Platform** requires multi-agent coordination across desktop development (Tauri/Rust), AI audio/diarization pipelines (Python/WhisperX), vector memory engines (Qdrant/SQLite), and autonomous action tools (FastMCP/Jira/GitHub). 

This guide maps each subsystem of our project to its corresponding skill from the skill directory (`~/.agents/skills/` & `~/.claude/skills/`).

---

## 🏗️ Skill Mapping by Project Subsystem

### 1. Core Architecture & Development (`Claude Code / CC`)
* **Primary Skills:**
  * **`codebase-design`**: To establish clean modular boundaries across Rust backend, Python audio service, and TypeScript frontend.
  * **`implement`**: End-to-end execution of new feature flows and core module implementations.
  * **`request-refactor-plan`**: Mandatory before executing breaking refactors in audio or memory pipelines.
  * **`code-reviewer`**: Automated security, performance, and memory-safety review on pull requests.
  * **`tdd` / `test-driven-development`**: Building resilient parsers for Whisper output and action engine payloads.

---

### 2. AI, MCP & Agent Engine (`Claude Code / CC`)
* **Primary Skills:**
  * **`mcp-builder`** *(CRITICAL)*: Building custom FastMCP servers to connect the AI Action Engine with external APIs (Jira, GitHub Issues, Slack, Google Calendar).
  * **`securing-agentic-ai-tool-invocation`**: Ensuring autonomous tool invocation cannot execute destructive or unintended external API calls.
  * **`implementing-llm-guardrails-for-security`**: Enforcing prompt boundaries and preventing malicious injection in user-supplied transcripts.
  * **`testing-prompt-injection-in-rag-pipelines`**: Auditing RAG retrieval vectors for prompt injection vulnerabilities.

---

### 3. Frontend & Real-Time HUD Overlay (`Claude Code / CC`)
* **Primary Skills:**
  * **`ui-ux-pro-max`**: Designing non-intrusive, real-time Heads-Up Display (HUD) overlay windows for live fact-checking.
  * **`design-an-interface`**: Crafting responsive desktop layouts for meeting transcripts, action items, and knowledge maps.
  * **`tailwind`**: Efficient utility-first styling for Tauri desktop frontend.
  * **`image-to-code`**: Converting UI wireframes and mockup screenshots directly into functional React/TypeScript components.

---

### 4. Memory, Vector DB & Orchestration (`CC_ONLY`)
* **Primary Skills:**
  * **`agentdb-memory-patterns`**: Architecting continuous meeting memory with vector retrieval and SQLite time-series storage.
  * **`swarm-orchestration` / `swarm-advanced`**: Coordinating multi-agent workflows (e.g., parallel transcription, diarization, and live RAG retrieval).
  * **`sparc-methodology`**: Structured engineering methodology for complex, multi-stage subsystem developments.

---

### 5. Product Management & Documentation (`Claude Chat / CHAT`)
* **Primary Skills:**
  * **`to-prd`**: Converting raw meeting assistant ideas into detailed Product Requirement Documents (PRDs).
  * **`decision-mapping`**: Documenting architectural trade-offs in `memory-bank/systemPatterns.md`.
  * **`workflow`**: Designing automated trigger-action chains for post-meeting workflows.

---

## 🎯 Recommended Execution Plan & Skill Invocation Sequence

```
[ Phase 1: Architecture & MCP Setup ]
  ├── Skill: "codebase-design" ──► Set up Tauri + Python + FastMCP layout
  └── Skill: "mcp-builder"    ──► Scaffold Jira/GitHub MCP integration servers

[ Phase 2: Core Audio & Memory Pipelines ]
  ├── Skill: "agentdb-memory-patterns" ──► Build local Qdrant/SQLite RAG storage
  └── Skill: "implement"              ──► Integrate WhisperX + PyAnnote diarization

[ Phase 3: Real-Time HUD & UX ]
  ├── Skill: "ui-ux-pro-max" ──► Design subtle overlay window for Fact-Checking
  └── Skill: "tailwind"      ──► Implement React/TS frontend overlay components

[ Phase 4: Security & Quality Assurance ]
  ├── Skill: "securing-agentic-ai-tool-invocation" ──► Guard autonomous tool execution
  └── Skill: "code-reviewer"                      ──► Audit codebase for safety & performance
```

---

## 💡 How to Invoke Skills in Prompts

To trigger any skill during development, use explicit prompt syntax:

* **Building MCP Tools:**
  > *"Use the `mcp-builder` skill to scaffold an MCP server exposing Jira issue creation and Slack notifications."*

* **Refactoring & Architecture:**
  > *"Use the `request-refactor-plan` skill to prepare a plan for decoupling the audio loopback engine from the LLM summary handler."*

* **Designing HUD UI:**
  > *"Use the `ui-ux-pro-max` skill to design a dark-mode real-time HUD notification card for live fact-checking alerts."*

---

**Author:** Yüksel Alp Çiğtekin  
**Repository Owner:** AlpC18  
**Last Updated:** October 2026
