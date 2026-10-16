// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { speakerTurns } from "./speakerTurns";
import type { StreamStatus, TranscriptSegment } from "./transcriptStream";
import { t } from "../i18n";

const STATUS_TEXT: Record<StreamStatus, string> = {
  connecting: "Connecting to the engine…",
  open: "Listening",
  closed: "Engine not running. Retrying…",
};

interface TranscriptFeedProps {
  status: StreamStatus;
  segments: readonly TranscriptSegment[];
}

/**
 * Live transcript list for the HUD: connection state on top, then one line
 * per speaker turn, each starting with who spoke. A segment in which several
 * people speak is shown as several lines; typed notes stand out. Presentation
 * only; all data comes from the engine's transcript stream.
 */
export function TranscriptFeed({ status, segments }: TranscriptFeedProps) {
  return (
    <section aria-label={t("Live transcript")}>
      <p role="status">{t(STATUS_TEXT[status])}</p>
      <ol aria-live="polite">
        {segments.flatMap((segment) =>
          speakerTurns(segment).map((turn, index) => (
            <li
              key={`${segment.source}-${segment.start}-${index}`}
              className={segment.source === "note" ? "my-1 border-l-4 border-amber-400 bg-amber-50 pl-2" : undefined}
            >
              <strong>{turn.speaker}:</strong> {turn.text}
            </li>
          )),
        )}
      </ol>
    </section>
  );
}
