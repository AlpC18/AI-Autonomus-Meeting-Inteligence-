// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { speakerTurns } from "./speakerTurns";
import { useTranscriptStream, type StreamStatus } from "./transcriptStream";

const STATUS_TEXT: Record<StreamStatus, string> = {
  connecting: "Connecting to the engine…",
  open: "Listening",
  closed: "Engine not running. Retrying…",
};

/**
 * Live transcript list for the HUD: connection state on top, then one line
 * per speaker turn, each starting with who spoke. A segment in which several
 * people speak is shown as several lines. Presentation only; all data comes
 * from the engine's transcript stream.
 */
export function TranscriptFeed() {
  const { status, segments } = useTranscriptStream();

  return (
    <section aria-label="Live transcript">
      <p role="status">{STATUS_TEXT[status]}</p>
      <ol aria-live="polite">
        {segments.flatMap((segment) =>
          speakerTurns(segment).map((turn, index) => (
            <li key={`${segment.source}-${segment.start}-${index}`}>
              <strong>{turn.speaker}:</strong> {turn.text}
            </li>
          )),
        )}
      </ol>
    </section>
  );
}
