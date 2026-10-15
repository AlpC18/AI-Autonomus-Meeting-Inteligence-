// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { useState } from "react";
import { AnswerView } from "./AskPanel";
import type { Answer, EngineCommand, LiveActionItem, MeetingSummaryEvent, TalkTime } from "./transcriptStream";

interface MeetingBarProps {
  title: string;
  connected: boolean;
  send: (message: EngineCommand) => boolean;
  lastSummary: MeetingSummaryEvent | null;
  brief: Answer | null;
  liveItems: readonly LiveActionItem[];
  lastTalkTime: readonly TalkTime[];
  /** Project the meeting is filed under; `null` when memory is off. */
  project: string | null;
  projectError: string | null;
}

function minutes(seconds: number): string {
  const whole = Math.round(seconds);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}

/**
 * The current meeting's title with an "End meeting" button, and the summary
 * of the meeting that ended last. Ending a meeting asks the engine to write
 * the AI summary into the notes, queue proposed actions for approval and
 * start the next meeting. A meeting titled from the calendar gets a brief of
 * what earlier meetings said about it; "Brief me" asks for it again.
 * Switching the project ends this meeting and files the next under it.
 */
export function MeetingBar({ title, connected, send, lastSummary, brief, liveItems, lastTalkTime, project, projectError }: MeetingBarProps) {
  const [ending, setEnding] = useState(false);
  const [nextProject, setNextProject] = useState("");
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
      {project !== null && (
        <form
          className="mt-2 flex items-center gap-2 text-sm"
          onSubmit={(event) => {
            event.preventDefault();
            const wanted = nextProject.trim();
            if (wanted && wanted !== project && send({ type: "switch_project", project: wanted })) setNextProject("");
          }}
        >
          <span className="text-zinc-600">Project: {project}</span>
          <input
            aria-label="Switch project"
            value={nextProject}
            maxLength={64}
            placeholder="another project"
            onChange={(event) => setNextProject(event.target.value)}
            className="rounded-md border border-zinc-300 px-2 py-1"
          />
          <button
            type="submit"
            disabled={!connected || !nextProject.trim()}
            className="cursor-pointer rounded-md border border-zinc-400 px-3 py-1 hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Switch
          </button>
        </form>
      )}
      {projectError && (
        <p role="alert" className="mt-1 text-sm text-red-700">
          Could not switch project: {projectError}
        </p>
      )}
      {brief && (
        <div aria-label="Brief from earlier meetings" className="mt-2 rounded-md border border-zinc-200 p-3">
          <h3 className="text-sm font-semibold">From earlier meetings</h3>
          <AnswerView answer={brief} />
        </div>
      )}
      {liveItems.length > 0 && (
        <div aria-label="Action items so far" className="mt-2 rounded-md border border-zinc-200 p-3 text-sm">
          <h3 className="font-semibold">Action items so far</h3>
          <ul className="mt-1 list-disc pl-5">
            {liveItems.map((item) => (
              <li key={`${item.task}|${item.owner ?? ""}`}>
                {item.task}
                {(item.owner || item.due) && (
                  <span className="text-zinc-600">
                    {" "}
                    ({[item.owner, item.due && `due ${item.due}`].filter(Boolean).join(", ")})
                  </span>
                )}
              </li>
            ))}
          </ul>
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
      {lastTalkTime.length > 0 && (
        <table aria-label="Talk time in the last meeting" className="mt-2 text-sm">
          <thead>
            <tr className="text-left text-zinc-600">
              <th className="pr-4 font-medium">Speaker</th>
              <th className="pr-4 font-medium">Talk time</th>
              <th className="pr-4 font-medium">Longest turn</th>
              <th className="font-medium">Interruptions</th>
            </tr>
          </thead>
          <tbody>
            {lastTalkTime.map((row) => (
              <tr key={row.speaker}>
                <td className="pr-4">{row.speaker}</td>
                <td className="pr-4">
                  {minutes(row.seconds)} ({Math.round(row.share * 100)}%)
                </td>
                <td className="pr-4">{minutes(row.longestSeconds)}</td>
                <td>{row.interruptions}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
