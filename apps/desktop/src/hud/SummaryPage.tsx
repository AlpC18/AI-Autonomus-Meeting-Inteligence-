// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { LastSummary } from "./MeetingBar";
import { Timeline } from "./Timeline";
import type { EngineCommand, MeetingSummaryEvent, Topic } from "./transcriptStream";
import { t } from "../i18n";

interface SummaryPageProps {
  connected: boolean;
  send: (message: EngineCommand) => boolean;
  /** The AI summary of the meeting that ended last, once it arrives. */
  summary: MeetingSummaryEvent | null;
  polishing: boolean;
  /** What the current meeting has talked about so far. */
  topics: readonly Topic[];
  back: () => void;
}

/**
 * What was talked about: the summary of the meeting that ended last, and the
 * current meeting's timeline so far. Without a summary yet, ending the
 * meeting from here asks the engine to write one.
 */
export function SummaryPage({ connected, send, summary, polishing, topics, back }: SummaryPageProps) {
  return (
    <section aria-label={t("Summary")} className="space-y-5">
      <div className="flex items-center gap-3">
        <h2 className="text-lg font-semibold">{t("Summary")}</h2>
        <button type="button" onClick={back} className="cursor-pointer rounded-md border border-zinc-400 px-3 py-1.5 text-sm hover:bg-zinc-100">
          {t("Back to the live meeting")}
        </button>
      </div>
      {polishing && <p role="status" className="text-sm text-zinc-600">{t("Making the transcript accurate… The notes and summary follow in a few minutes.")}</p>}
      {summary ? (
        <LastSummary summary={summary} />
      ) : (
        <div className="rounded-xl border border-zinc-200 bg-surface p-4 text-sm">
          <p className="text-zinc-700">{t("No summary yet. End the meeting and the AI summary appears here.")}</p>
          <button
            type="button"
            disabled={!connected}
            onClick={() => send({ type: "end_meeting" })}
            className="mt-3 cursor-pointer rounded-md bg-accent px-3 py-1.5 font-medium text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {t("End meeting and summarize")}
          </button>
        </div>
      )}
      <Timeline topics={topics} />
    </section>
  );
}
