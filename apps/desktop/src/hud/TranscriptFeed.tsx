// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { useEffect, useRef } from "react";
import { speakerTurns } from "./speakerTurns";
import { displaySpeaker, speakerColor } from "./speakers";
import { captionKey, type StreamStatus, type TranscriptSegment } from "./transcriptStream";
import { timeOf } from "./Timeline";
import { t } from "../i18n";

const STATUS_TEXT: Record<StreamStatus, string> = {
  connecting: "Connecting to the engine…",
  open: "Listening",
  closed: "Engine not running. Retrying…",
};

/** Lines within this many pixels of the bottom count as "following" the transcript. */
const FOLLOW_SLACK_PX = 80;

interface TranscriptFeedProps {
  status: StreamStatus;
  segments: readonly TranscriptSegment[];
  /** Live translations by segment (see `captionKey`); shown under each line. */
  captions?: Readonly<Record<string, string>>;
}

/** The transcript is shown in blocks of this many minutes of wall-clock time. */
export const BLOCK_MINUTES = 2;
export const BLOCK_MS = BLOCK_MINUTES * 60_000;

/** What one person said in a row within a block, with any translations of it. */
interface Paragraph {
  speaker: string;
  text: string;
  note: boolean;
  captions: string[];
}

interface Block {
  from: number;
  paragraphs: Paragraph[];
}

/** Wall-clock start of a segment in ms; the engine's seconds stand in when it has no stamp. */
const wallTime = (segment: TranscriptSegment) => segment.at ?? segment.start * 1000;

/** Local time of day of `ms`, written as the timeline writes it ("12:00"). */
export const timeOfDay = (ms: number) => timeOf(new Date(ms).toISOString());

/**
 * Groups segments into blocks of {@link BLOCK_MINUTES} on the clock (12:00–12:02,
 * 12:02–12:04, …), joining what one person said in a row into one paragraph.
 */
export function transcriptBlocks(segments: readonly TranscriptSegment[], captions: Readonly<Record<string, string>> = {}): Block[] {
  const blocks: Block[] = [];
  for (const segment of segments) {
    const from = Math.floor(wallTime(segment) / BLOCK_MS) * BLOCK_MS;
    if (blocks.length === 0 || blocks[blocks.length - 1].from !== from) blocks.push({ from, paragraphs: [] });
    const { paragraphs } = blocks[blocks.length - 1];
    const note = segment.source === "note";
    const turns = speakerTurns(segment);
    turns.forEach((turn, index) => {
      const caption = index === turns.length - 1 ? captions[captionKey(segment.source, segment.start)] : undefined;
      const last = paragraphs[paragraphs.length - 1];
      if (last && !note && !last.note && last.speaker === turn.speaker) {
        paragraphs[paragraphs.length - 1] = {
          ...last,
          text: `${last.text} ${turn.text.trim()}`,
          captions: caption ? [...last.captions, caption] : last.captions,
        };
      } else {
        paragraphs.push({ speaker: turn.speaker, text: turn.text.trim(), note, captions: caption ? [caption] : [] });
      }
    });
  }
  return blocks;
}

/**
 * The live transcript in two-minute blocks of clock time, what each person
 * said in a row as one paragraph in their own colour, typed notes highlighted. It follows new lines unless the user has
 * scrolled up to read. Presentation only; data comes from the engine's stream.
 */
export function TranscriptFeed({ status, segments, captions = {} }: TranscriptFeedProps) {
  const list = useRef<HTMLOListElement>(null);
  const following = useRef(true);

  useEffect(() => {
    const element = list.current;
    if (element && following.current) element.scrollTop = element.scrollHeight;
  }, [segments, captions]);

  const onScroll = () => {
    const element = list.current;
    if (element) following.current = element.scrollHeight - element.scrollTop - element.clientHeight < FOLLOW_SLACK_PX;
  };

  return (
    <section aria-label={t("Live transcript")} className="rounded-xl border border-zinc-200 bg-surface">
      <header className="flex items-center justify-between border-b border-zinc-200 px-4 py-2.5">
        <h2 className="text-sm font-semibold">{t("Live transcript")}</h2>
        <p role="status" className="flex items-center gap-1.5 text-xs text-zinc-600">
          <span aria-hidden="true" className={`size-1.5 rounded-full ${status === "open" ? "bg-accent" : "bg-zinc-400"}`} />
          {t(STATUS_TEXT[status])}
        </p>
      </header>
      {segments.length === 0 ? (
        <p className="px-4 py-10 text-center text-sm text-zinc-500">{t("Waiting for someone to speak…")}</p>
      ) : (
        <ol aria-live="polite" ref={list} onScroll={onScroll} className="max-h-[60vh] min-h-48 space-y-4 overflow-y-auto px-4 py-3">
          {transcriptBlocks(segments, captions).map((block) => (
            <li key={block.from}>
              <h3 className="sticky top-0 mb-1.5 bg-surface py-0.5 text-xs font-medium text-zinc-500 tabular-nums">
                {timeOfDay(block.from)} – {timeOfDay(block.from + BLOCK_MS)}
              </h3>
              <div className="space-y-2">
                {block.paragraphs.map((paragraph, index) => (
                  <div key={index} className={paragraph.note ? "rounded-lg border-l-4 border-amber-400 bg-amber-50 px-3 py-1.5" : ""}>
                    <p className="text-[15px] leading-relaxed">
                      <strong className={`font-semibold ${paragraph.note ? "" : speakerColor(paragraph.speaker)}`}>{displaySpeaker(paragraph.speaker)}</strong>{" "}
                      <span className="text-zinc-900">{paragraph.text}</span>
                    </p>
                    {paragraph.captions.length > 0 && (
                      <p lang="" aria-label={t("Translation")} className="text-sm text-zinc-600 italic">
                        {paragraph.captions.join(" ")}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
