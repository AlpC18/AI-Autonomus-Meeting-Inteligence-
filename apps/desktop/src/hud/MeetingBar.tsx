// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { useState } from "react";
import { AnswerView } from "./AskPanel";
import type { Answer, EngineCommand, MeetingSummaryEvent } from "./transcriptStream";

interface MeetingBarProps {
  title: string;
  connected: boolean;
  send: (message: EngineCommand) => boolean;
  lastSummary: MeetingSummaryEvent | null;
  brief: Answer | null;
}

/**
 * The current meeting's title with an "End meeting" button, and the summary
 * of the meeting that ended last. Ending a meeting asks the engine to write
 * the AI summary into the notes, queue proposed actions for approval and
 * start the next meeting. A meeting titled from the calendar gets a brief of
 * what earlier meetings said about it; "Brief me" asks for it again.
 */
export function MeetingBar({ title, connected, send, lastSummary, brief }: MeetingBarProps) {
  const [ending, setEnding] = useState(false);
  const [shownSummary, setShownSummary] = useState<MeetingSummaryEvent | null>(null);
  // A summary arriving after "End meeting" finishes the ending state.
  if (lastSummary !== shownSummary) {
    setShownSummary(lastSummary);
    setEnding(false);
  }

  const end = () => {
    if (send({ type: "end_meeting" })) setEnding(true);
  };

  return (
    <section aria-label="Current meeting" className="mt-3">
      <div className="flex items-center gap-3">
        <h2 className="text-lg font-semibold">{title}</h2>
        <button
          type="button"
          disabled={!connected || ending}
          onClick={end}
          className="cursor-pointer rounded-md border border-zinc-400 px-3 py-1.5 text-sm hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {ending ? "Ending…" : "End meeting"}
        </button>
        <button
          type="button"
          disabled={!connected}
          onClick={() => send({ type: "brief" })}
          className="cursor-pointer rounded-md border border-zinc-400 px-3 py-1.5 text-sm hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Brief me
        </button>
      </div>
      {brief && (
        <div aria-label="Brief from earlier meetings" className="mt-2 rounded-md border border-zinc-200 p-3">
          <h3 className="text-sm font-semibold">From earlier meetings</h3>
          <AnswerView answer={brief} />
        </div>
      )}
      {lastSummary && (
        <div role="status" className="mt-2 rounded-md bg-zinc-50 p-3 text-sm">
          {lastSummary.error ? (
            <p className="text-red-700">The summary could not be made: {lastSummary.error}</p>
          ) : (
            <pre className="whitespace-pre-wrap">{lastSummary.markdown}</pre>
          )}
          {lastSummary.queued > 0 && (
            <p className="mt-1 text-zinc-700">
              {lastSummary.queued} proposed action(s) are waiting for your approval below.
            </p>
          )}
          {lastSummary.errors.map((error) => (
            <p key={error} className="text-xs text-zinc-600">
              Not proposed: {error}
            </p>
          ))}
        </div>
      )}
    </section>
  );
}
