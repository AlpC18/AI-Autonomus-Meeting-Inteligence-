// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

/**
 * HUD module: the real-time fact-checking overlay.
 *
 * Owns only the presentation of live alerts. It must not capture audio, query
 * memory, or dispatch actions; those arrive as data from the backend.
 * Phase 2 provides the live transcript feed; fact-check alerts come in Phase 3.
 */
export { TranscriptFeed } from "./TranscriptFeed";
export { useTranscriptStream } from "./transcriptStream";
