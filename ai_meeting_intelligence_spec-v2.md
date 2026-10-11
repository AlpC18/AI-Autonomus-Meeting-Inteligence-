# Spec Document: Next-Gen Autonomous AI Meeting & Workflow Agent

## 📌 Executive Summary & Context
This specification document is designed to guide Claude (or an AI/Engineer team) in building a state-of-the-art **Autonomous AI Meeting Intelligence Platform**. 

Existing open-source meeting tools and SaaS solutions (e.g., Fireflies, Otter) focus almost exclusively on passive transcription and basic text summaries. This project aims to combine the strongest open-source foundation repositories into a unified architecture while building **active, action-oriented, real-time intelligence layers** on top (e.g., Live Fact-Checking, Codebase Context Mapping, and Autonomous Task Execution).

---

## 🔗 Foundation Open-Source Repositories to Merge & Leverage

To avoid reinventing the wheel, the core engine will merge architecture and modules from the following high-star open-source repositories:

1. **[Zackriya-Solutions/meetily](https://github.com/Zackriya-Solutions/meetily) (~31k+ ★)**
   * **Role:** Desktop audio loopback capture (system audio + mic without meeting bots) & Local Whisper + Ollama pipeline.
2. **[chime-vc/buzz](https://github.com/chime-vc/buzz) (~20k+ ★)**
   * **Role:** High-performance offline audio transcription, translation, and local Whisper integration.
3. **[screenpipe/screenpipe](https://github.com/screenpipe/screenpipe) (~18.5k+ ★)**
   * **Role:** 24/7 background desktop audio/screen memory, Rust/Tauri architecture, embedded SQLite & Vector DB for local RAG retrieval.
4. **Anarlog / Hyprnote (~8.9k+ ★)**
   * **Role:** Markdown-centric notepad UX for real-time human note blending with live transcription.
5. **[m-bain/whisperX](https://github.com/m-bain/whisperx)**
   * **Role:** Word-level timestamped transcription with speaker diarization (PyAnnote integration).

---

## 🏗️ Unified Core Architecture

```
[ System Audio / Mic Input ] ──► [ WhisperX / Faster-Whisper + PyAnnote ] ──► Speaker-Diarized Stream
                                                                                   │
[ Real-Time Human Notes ] ─────────────────────────────────────────────────────────┼──► [ Local Vector RAG ]
                                                                                   │     (Qdrant/Chroma)
[ Codebase & Past Docs ] ──────────────────────────────────────────────────────────┘        │
                                                                                           ▼
                                                                                [ Claude / Ollama LLM ]
                                                                                           │
                                                                                           ▼
                                                                           [ Otonom Action & Fact HUD ]
```

1. **Audio Capture Engine:** Botless desktop audio loopback capturing speaker and microphone streams separately.
2. **Diarization & Transcription:** Real-time word-level timestamps with speaker identification (`whisperX` + `faster-whisper`).
3. **Local Vector & RAG Memory:** Persistent SQLite + Vector DB storing all historical meetings, documents, and transcripts (`screenpipe` approach).
4. **Hybrid UX Notepad:** Real-time human notes merged with live transcripts (`Anarlog` approach).

---

## 🚀 Novel & Missing Features to Implement (The "Killer" Features)

The primary value proposition of this project lies in features that DO NOT exist in current market alternatives:

### 1. Real-Time HUD: Live "Fact-Checking" & Cross-Referencing
* **Problem:** Attendees misquote past decisions, budgets, or technical specifications during meetings.
* **Feature:** The system continuously runs RAG queries in the background against historical meeting logs and company documents.
* **Behavior:** When a conflict occurs (e.g., someone states *"The budget was $50k"*), a subtle notification appears on the user's HUD:
  > ⚠️ *Fact-Check Alert: In the Aug 14 meeting, the budget was revised down to $35k.*

### 2. Autonomous Action Engine (Beyond Text Summaries)
* **Problem:** Current meeting tools generate passive bulleted text like *"John will create a Jira ticket"* without acting.
* **Feature:** Direct API integrations (Jira, GitHub, Slack, Notion, Google Calendar) to convert spoken commitments into executed tasks.
* **Behavior:** Post-meeting, the AI prompts for approval:
  > 🤖 *"Created Jira ticket 'Refactor Payment API' for John, set deadline to Tuesday, and sent notification on Slack. Approve execution?"*

### 3. Codebase & Architecture Context Mapping
* **Problem:** Meeting assistants lack understanding of software codebases and technical architecture.
* **Feature:** Deep integration with GitHub/GitLab repositories and technical specs.
* **Behavior:** When engineers discuss adding a feature (e.g., *"Let's integrate Stripe"*), the AI scans the codebase and reports:
  > 💡 *Code Context: `/services/payment` currently uses Paddle. Integrating Stripe will impact 3 specific controller files.*

### 4. Risk & Commitment Tracking (Over-promising & Sentiment Analysis)
* **Problem:** Over-promising delivery dates or ignoring stakeholder hesitation leads to missed deadlines.
* **Feature:**
  * **Over-Commitment Detection:** Compares spoken deadlines against current team capacity/sprint load and warns if unrealistic.
  * **Hesitation & Sentiment Anchoring:** Timestamp markers where clients or team members show indecision or doubt.

### 5. Multi-Tenant Project Context Isolation
* **Problem:** Context leakage across different client projects in shared vector databases.
* **Feature:** Strict project-level isolation boundaries preventing cross-client data retrieval during RAG queries.

---

## 📊 Feature Comparison Matrix

| Feature | Meetily / Fireflies | Screenpipe | Anarlog | **Our Project Spec** |
| :--- | :---: | :---: | :---: | :---: |
| **Audio Transcription & Summary** | ✅ | ✅ | ✅ | ✅ |
| **Speaker Diarization** | ✅ | ❌ | ✅ | ✅ |
| **Desktop Background Memory (RAG)** | ❌ | ✅ | ❌ | ✅ |
| **Real-Time Fact-Checking HUD** | ❌ | ❌ | ❌ | **✅ (New)** |
| **Autonomous API Actions (Jira/GitHub)** | ❌ (Text only) | ❌ | ❌ | **✅ (New)** |
| **Codebase Architecture Mapping** | ❌ | ❌ | ❌ | **✅ (New)** |
| **Over-Promising & Risk Tracking** | ❌ | ❌ | ❌ | **✅ (New)** |
| **Strict Project Context Isolation** | ❌ | ⚠️ | ❌ | **✅ (New)** |

---

## 🛠️ Recommended Tech Stack

* **Desktop Application / UI:** Tauri (Rust + React / TypeScript) or Electron
* **Audio Engine:** Python (`faster-whisper`, `whisperX`, `pyannote.audio`)
* **Vector Database:** Embedded Qdrant or ChromaDB
* **LLM Orchestration:** LangChain / LlamaIndex / Claude Code CLI / Ollama
* **Integration Layer:** FastMCP (Model Context Protocol) / Webhooks for Jira, GitHub, Slack, Calendar
