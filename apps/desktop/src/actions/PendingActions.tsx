// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { useCallback, useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

/** A GitHub issue the assistant proposed and that awaits the user's decision. */
interface PendingIssue {
  id: string;
  repo: string;
  title: string;
  body: string;
  labels: string[];
}

const REFRESH_MS = 5000;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/**
 * Keeps only well-formed GitHub issue proposals from the backend's reply, so
 * the user is never asked to approve something the app cannot show in full.
 */
function parsePending(reply: unknown): PendingIssue[] {
  if (!Array.isArray(reply)) return [];
  return reply.flatMap((item): PendingIssue[] => {
    if (!isRecord(item) || typeof item.id !== "string" || item.kind !== "github_issue") return [];
    const payload = item.payload;
    if (!isRecord(payload) || typeof payload.repo !== "string" || typeof payload.title !== "string") {
      return [];
    }
    const labels = Array.isArray(payload.labels)
      ? payload.labels.filter((label): label is string => typeof label === "string")
      : [];
    const body = typeof payload.body === "string" ? payload.body : "";
    return [{ id: item.id, repo: payload.repo, title: payload.title, body, labels }];
  });
}

/** Reads the outcome of a decision from the backend's reply. */
function describeOutcome(reply: unknown): string {
  const action = Array.isArray(reply) ? reply[0] : undefined;
  if (!isRecord(action) || typeof action.status !== "string") return "Decision recorded.";
  const result = typeof action.result === "string" ? action.result : "";
  if (action.status === "done") return `Created: ${result}`;
  if (action.status === "rejected") return "Rejected. Nothing was sent.";
  return `Failed: ${result || "no details given"}`;
}

/**
 * Review panel for actions the assistant proposed.
 *
 * Shows each proposal in full (repository, title, labels, body) with Approve
 * and Reject buttons. Nothing leaves the machine until Approve is pressed, and
 * an approved action runs exactly once. The list refreshes every five seconds.
 */
export function PendingActions() {
  const [issues, setIssues] = useState<PendingIssue[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const refresh = useCallback(() => {
    invoke<unknown>("pending_actions")
      .then((reply) => setIssues(parsePending(reply)))
      .catch((cause: unknown) => setNotice(`Could not load proposed actions: ${String(cause)}`));
  }, []);

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const decide = (id: string, approve: boolean) => {
    setBusy(id);
    invoke<unknown>("decide_action", { id, approve })
      .then((reply) => setNotice(describeOutcome(reply)))
      .catch((cause: unknown) => setNotice(`Could not complete that: ${String(cause)}`))
      .finally(() => {
        setBusy(null);
        refresh();
      });
  };

  return (
    <section aria-label="Proposed actions" className="mt-6">
      <h2 className="text-lg font-semibold">Proposed actions</h2>
      {notice && (
        <p role="status" className="mt-2 text-sm break-words text-zinc-700">
          {notice}
        </p>
      )}
      {issues.length === 0 && <p className="mt-2 text-sm text-zinc-600">Nothing is waiting for you.</p>}
      <ul className="mt-2 flex flex-col gap-3">
        {issues.map((issue) => (
          <li key={issue.id} className="rounded-lg border border-zinc-300 p-3">
            <p className="text-xs text-zinc-600">GitHub issue in {issue.repo}</p>
            <h3 className="font-semibold">{issue.title}</h3>
            {issue.labels.length > 0 && (
              <p className="text-xs text-zinc-600">Labels: {issue.labels.join(", ")}</p>
            )}
            {issue.body && (
              <pre className="mt-1 max-h-40 overflow-auto text-sm whitespace-pre-wrap">{issue.body}</pre>
            )}
            <div className="mt-2 flex gap-2">
              <button
                type="button"
                disabled={busy !== null}
                onClick={() => decide(issue.id, true)}
                className="cursor-pointer rounded-md bg-zinc-900 px-3 py-1.5 text-sm text-white hover:bg-zinc-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busy === issue.id ? "Working…" : "Approve and create"}
              </button>
              <button
                type="button"
                disabled={busy !== null}
                onClick={() => decide(issue.id, false)}
                className="cursor-pointer rounded-md border border-zinc-400 px-3 py-1.5 text-sm hover:bg-zinc-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Reject
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
