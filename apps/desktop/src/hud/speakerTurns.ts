// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import type { TranscriptSegment } from "./transcriptStream";

/** A run of consecutive words in a segment that one person said. */
export interface SpeakerTurn {
  speaker: string;
  text: string;
  /** Start of the first word, in seconds on the engine's timeline. */
  start: number;
}

/**
 * Splits a segment into runs of words by the same speaker, in spoken order.
 *
 * Words without a speaker of their own count as the segment's speaker. A
 * segment with one voice, or with no word timings, comes back as a single
 * turn holding the segment's own text.
 */
export function speakerTurns(segment: TranscriptSegment): SpeakerTurn[] {
  const turns: SpeakerTurn[] = [];
  for (const word of segment.words) {
    const speaker = word.speaker ?? segment.speaker;
    const last = turns[turns.length - 1];
    if (last && last.speaker === speaker) {
      turns[turns.length - 1] = { ...last, text: `${last.text} ${word.text.trim()}` };
    } else {
      turns.push({ speaker, text: word.text.trim(), start: word.start });
    }
  }
  if (turns.length < 2) {
    return [{ speaker: segment.speaker, text: segment.text, start: segment.start }];
  }
  return turns;
}
