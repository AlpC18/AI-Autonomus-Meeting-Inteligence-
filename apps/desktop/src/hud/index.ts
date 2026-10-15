// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

/**
 * HUD module: the real-time fact-checking overlay.
 *
 * Owns only the presentation of live alerts. It must not capture audio, query
 * memory, or dispatch actions; those arrive as data from the backend.
 * Provides the live transcript feed for the main window and the floating
 * fact-check overlay window.
 */
export { HudOverlay } from "./HudOverlay";
export { AskPanel } from "./AskPanel";
export { MeetingBar } from "./MeetingBar";
export { SpeakerNamer } from "./SpeakerNamer";
export { TranscriptFeed } from "./TranscriptFeed";
export { useTranscriptStream } from "./transcriptStream";
