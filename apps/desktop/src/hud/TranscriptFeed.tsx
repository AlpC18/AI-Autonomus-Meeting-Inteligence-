// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { useEffect, useRef } from "react";
import { speakerTurns } from "./speakerTurns";
import { displaySpeaker, speakerColor } from "./speakers";
import { captionKey, type StreamStatus, type TranscriptSegment } from "./transcriptStream";
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

function clock(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(whole / 60);
  return `${String(minutes).padStart(2, "0")}:${String(whole % 60).padStart(2, "0")}`;
}

/**
 * The live transcript: one line per speaker turn, the speaker in their own
 * colour, typed notes highlighted. It follows new lines unless the user has
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
        <ol aria-live="polite" ref={list} onScroll={onScroll} className="max-h-[60vh] min-h-48 space-y-3 overflow-y-auto px-4 py-3">
          {segments.flatMap((segment) => {
            const caption = captions[captionKey(segment.source, segment.start)];
            const note = segment.source === "note";
            return [
              ...speakerTurns(segment).map((turn, index) => (
                <li
                  key={`${segment.source}-${segment.start}-${index}`}
                  className={note ? "rounded-lg border-l-4 border-amber-400 bg-amber-50 px-3 py-1.5" : "grid grid-cols-[3.25rem_1fr] gap-x-2"}
                >
                  {!note && <span className="pt-0.5 text-xs text-zinc-500 tabular-nums">{clock(segment.start)}</span>}
                  <p className="text-[15px] leading-relaxed">
                    <strong className={`font-semibold ${note ? "" : speakerColor(turn.speaker)}`}>{displaySpeaker(turn.speaker)}</strong>{" "}
                    <span className="text-zinc-900">{turn.text}</span>
                  </p>
                </li>
              )),
              ...(caption
                ? [
                    <li key={`${segment.source}-${segment.start}-caption`} lang="" aria-label={t("Translation")} className="pl-[3.75rem] text-sm text-zinc-600 italic">
                      {caption}
                    </li>,
                  ]
                : []),
            ];
          })}
        </ol>
      )}
    </section>
  );
}
