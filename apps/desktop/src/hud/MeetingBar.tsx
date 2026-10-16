// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { openUrl } from "@tauri-apps/plugin-opener";
import { AnswerView } from "./AskPanel";
import type { Answer, DocumentImport, EngineCommand, LiveActionItem, MeetingSummaryEvent, TalkTime } from "./transcriptStream";
import { t } from "../i18n";

/** Asks the user for documents with the system file picker; `null` when cancelled. */
async function pickDocuments(): Promise<string[] | null> {
  const picked = await open({
    multiple: true,
    title: t("Add documents to this project's memory"),
    filters: [{ name: t("Documents"), extensions: ["md", "markdown", "txt", "pdf"] }],
  });
  return picked === null ? null : Array.isArray(picked) ? picked : [picked];
}

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
  /** What the live hints found in the meeting that ended last (Markdown). */
  lastReport?: string | null;
  lastImport?: DocumentImport | null;
  /** Chooses documents to import; the system file picker unless replaced (in tests). */
  pick?: () => Promise<string[] | null>;
}

/** Mail-app link for `email`; the body is cut so the link stays within what mail apps accept. */
export function mailtoLink(email: { subject: string; body: string }): string {
  return `mailto:?subject=${encodeURIComponent(email.subject)}&body=${encodeURIComponent(email.body.slice(0, MAX_MAILTO_BODY))}`;
}

const MAX_MAILTO_BODY = 1800;

/** Buttons to copy the follow-up e-mail or open it in the user's mail app. */
function FollowUp({ email }: { email: { subject: string; body: string } }) {
  const [copied, setCopied] = useState<string | null>(null);
  const copy = () =>
    void navigator.clipboard
      .writeText(`${email.subject}\n\n${email.body}`)
      .then(() => setCopied(t("Copied.")))
      .catch(() => setCopied(t("Could not copy; use Open in mail app.")));
  return (
    <div className="mt-2 flex items-center gap-2">
      <button type="button" onClick={copy} className="cursor-pointer rounded-md border border-zinc-400 px-3 py-1 hover:bg-zinc-100">
        {t("Copy follow-up email")}
      </button>
      <button
        type="button"
        onClick={() => void openUrl(mailtoLink(email)).catch(() => setCopied(t("No mail app answered.")))}
        className="cursor-pointer rounded-md border border-zinc-400 px-3 py-1 hover:bg-zinc-100"
      >
        {t("Open in mail app")}
      </button>
      {copied && <span className="text-xs text-zinc-600">{copied}</span>}
    </div>
  );
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
export function MeetingBar({ title, connected, send, lastSummary, brief, liveItems, lastTalkTime, project, projectError, lastReport = null, lastImport = null, pick = pickDocuments }: MeetingBarProps) {
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
    <section aria-label={t("Current meeting")} className="mt-3">
      <div className="flex items-center gap-3">
        <h2 className="text-lg font-semibold">{title}</h2>
        <button
          type="button"
          disabled={!connected || ending}
          onClick={end}
          className="cursor-pointer rounded-md border border-zinc-400 px-3 py-1.5 text-sm hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {ending ? t("Ending…") : t("End meeting")}
        </button>
        <button
          type="button"
          disabled={!connected}
          onClick={() => send({ type: "brief" })}
          className="cursor-pointer rounded-md border border-zinc-400 px-3 py-1.5 text-sm hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {t("Brief me")}
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
          <span className="text-zinc-600">{t("Project: {project}", { project })}</span>
          <input
            aria-label={t("Switch project")}
            value={nextProject}
            maxLength={64}
            placeholder={t("another project")}
            onChange={(event) => setNextProject(event.target.value)}
            className="rounded-md border border-zinc-300 px-2 py-1"
          />
          <button
            type="submit"
            disabled={!connected || !nextProject.trim()}
            className="cursor-pointer rounded-md border border-zinc-400 px-3 py-1 hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {t("Switch")}
          </button>
          <button
            type="button"
            disabled={!connected}
            title={t("Company documents in memory are used by fact checks and answers.")}
            onClick={() =>
              void pick()
                .then((paths) => paths && paths.length > 0 && send({ type: "import_documents", paths }))
                .catch(() => undefined)
            }
            className="cursor-pointer rounded-md border border-zinc-400 px-3 py-1 hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {t("Add documents…")}
          </button>
        </form>
      )}
      {lastImport && (
        <div role="status" aria-label={t("Document import")} className="mt-1 text-sm text-zinc-700">
          {lastImport.imported.map((item) => (
            <p key={item.name}>
              {t("Added {name} ({count} passages)", { name: item.name, count: item.passages })}
            </p>
          ))}
          {lastImport.errors.map((error) => (
            <p key={error} className="text-red-700">
              {t("Not added: {error}", { error })}
            </p>
          ))}
        </div>
      )}
      {projectError && (
        <p role="alert" className="mt-1 text-sm text-red-700">
          {t("Could not switch project: {error}", { error: projectError })}
        </p>
      )}
      {brief && (
        <div aria-label={t("Brief from earlier meetings")} className="mt-2 rounded-md border border-zinc-200 p-3">
          <h3 className="text-sm font-semibold">{t("From earlier meetings")}</h3>
          <AnswerView answer={brief} />
        </div>
      )}
      {liveItems.length > 0 && (
        <div aria-label={t("Action items so far")} className="mt-2 rounded-md border border-zinc-200 p-3 text-sm">
          <h3 className="font-semibold">{t("Action items so far")}</h3>
          <ul className="mt-1 list-disc pl-5">
            {liveItems.map((item) => (
              <li key={`${item.task}|${item.owner ?? ""}`}>
                {item.task}
                {(item.owner || item.due) && (
                  <span className="text-zinc-600">
                    {" "}
                    ({[item.owner, item.due && t("due {date}", { date: item.due })].filter(Boolean).join(", ")})
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
            <p className="text-red-700">{t("The summary could not be made: {error}", { error: lastSummary.error })}</p>
          ) : (
            <pre className="whitespace-pre-wrap">{lastSummary.markdown}</pre>
          )}
          {lastSummary.queued > 0 && (
            <p className="mt-1 text-zinc-700">
              {t("{count} proposed action(s) are waiting for your approval below.", { count: lastSummary.queued })}
            </p>
          )}
          {lastSummary.errors.map((error) => (
            <p key={error} className="text-xs text-zinc-600">
              {t("Not proposed: {error}", { error })}
            </p>
          ))}
          {lastSummary.email && <FollowUp email={lastSummary.email} />}
        </div>
      )}
      {lastReport && (
        <pre aria-label={t("Hints from the last meeting")} className="mt-2 whitespace-pre-wrap rounded-md bg-zinc-50 p-3 text-sm">
          {lastReport}
        </pre>
      )}
      {lastTalkTime.length > 0 && (
        <table aria-label={t("Talk time in the last meeting")} className="mt-2 text-sm">
          <thead>
            <tr className="text-left text-zinc-600">
              <th className="pr-4 font-medium">{t("Speaker")}</th>
              <th className="pr-4 font-medium">{t("Talk time")}</th>
              <th className="pr-4 font-medium">{t("Longest turn")}</th>
              <th className="font-medium">{t("Interruptions")}</th>
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
