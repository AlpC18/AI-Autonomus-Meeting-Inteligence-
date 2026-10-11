// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { useTranscriptStream, type StreamStatus } from "./transcriptStream";

const STATUS_TEXT: Record<StreamStatus, string> = {
  connecting: "Connecting to the engine…",
  open: "Listening",
  closed: "Engine not running. Retrying…",
};

/**
 * Live transcript list for the HUD: connection state on top, then one line
 * per segment with its speaker. Presentation only; all data comes from the
 * engine's transcript stream.
 */
export function TranscriptFeed() {
  const { status, segments } = useTranscriptStream();

  return (
    <section aria-label="Live transcript">
      <p role="status">{STATUS_TEXT[status]}</p>
      <ol aria-live="polite">
        {segments.map((segment) => (
          <li key={`${segment.source}-${segment.start}`}>
            <strong>{segment.speaker}:</strong> {segment.text}
          </li>
        ))}
      </ol>
    </section>
  );
}
