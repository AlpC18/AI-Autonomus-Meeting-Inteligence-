# Engine Features

Log every new feature, AI prompt template, or pipeline update here (`AI_GUIDELINES.md` §3). Newest first.

| Date | Module | Feature | Notes |
| :--- | :--- | :--- | :--- |
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
