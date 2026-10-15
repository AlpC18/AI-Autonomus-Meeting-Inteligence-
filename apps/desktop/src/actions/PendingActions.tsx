// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { useCallback, useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

/** An action the assistant proposed, laid out for the user's decision. */
interface PendingAction {
  id: string;
  /** What it is and where it goes, e.g. "GitHub issue in acme/website". */
  heading: string;
  title: string;
  /** Extra facts shown under the title, e.g. the labels. */
  detail: string;
  /** The full text that would be sent. */
  body: string;
  /** Wording of the approve button, e.g. "Approve and send". */
  approveLabel: string;
}

type Layout = Omit<PendingAction, "id">;

const REFRESH_MS = 5000;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function text(value: unknown): string {
  return typeof value === "string" ? value : "";
}

/** Lays out one proposal by kind, or returns `null` if it cannot be shown in full. */
function layOut(kind: unknown, payload: Record<string, unknown>): Layout | null {
  if (kind === "github_issue" && typeof payload.repo === "string" && text(payload.title)) {
    const labels = Array.isArray(payload.labels)
      ? payload.labels.filter((label): label is string => typeof label === "string")
      : [];
    return {
      heading: `GitHub issue in ${payload.repo}`,
      title: text(payload.title),
      detail: labels.length > 0 ? `Labels: ${labels.join(", ")}` : "",
      body: text(payload.body),
      approveLabel: "Approve and create",
    };
  }
  if (kind === "jira_issue" && text(payload.project) && text(payload.summary)) {
    const labels = Array.isArray(payload.labels)
      ? payload.labels.filter((label): label is string => typeof label === "string")
      : [];
    return {
      heading: `Jira task in project ${text(payload.project)}`,
      title: text(payload.summary),
      detail: labels.length > 0 ? `Labels: ${labels.join(", ")}` : "",
      body: text(payload.body),
      approveLabel: "Approve and create",
    };
  }
  if (kind === "slack_message" && text(payload.text)) {
    return {
      heading: "Slack message to your configured channel",
      title: "",
      detail: "",
      body: text(payload.text),
      approveLabel: "Approve and send",
    };
  }
  if (kind === "calendar_deadline" && text(payload.due) && text(payload.title)) {
    return {
      heading: "Google Calendar deadline",
      title: text(payload.title),
      detail: `Due: ${text(payload.due)} (all day)`,
      body: text(payload.description),
      approveLabel: "Approve and schedule",
    };
  }
  if (kind === "email_recap" && text(payload.subject) && Array.isArray(payload.to)) {
    const to = payload.to.filter((address): address is string => typeof address === "string");
    if (to.length === 0) return null;
    return {
      heading: "E-mail from your Gmail",
      title: text(payload.subject),
      detail: `To: ${to.join(", ")}`,
      body: text(payload.body),
      approveLabel: "Approve and send",
    };
  }
  return null;
}

/**
 * Keeps only proposals of a known kind with every required field, so the
 * user is never asked to approve something the app cannot show in full.
 */
function parsePending(reply: unknown): PendingAction[] {
  if (!Array.isArray(reply)) return [];
  return reply.flatMap((item): PendingAction[] => {
    if (!isRecord(item) || typeof item.id !== "string" || !isRecord(item.payload)) return [];
    const layout = layOut(item.kind, item.payload);
    return layout ? [{ id: item.id, ...layout }] : [];
  });
}

/** Reads the outcome of a decision from the backend's reply. */
function describeOutcome(reply: unknown): string {
  const action = Array.isArray(reply) ? reply[0] : undefined;
  if (!isRecord(action) || typeof action.status !== "string") return "Decision recorded.";
  const result = typeof action.result === "string" ? action.result : "";
  if (action.status === "done") return `Done: ${result}`;
  if (action.status === "rejected") return "Rejected. Nothing was sent.";
  return `Failed: ${result || "no details given"}`;
}

/**
 * Review panel for actions the assistant proposed.
 *
 * Shows each proposal in full (what it is, where it goes and the exact text)
 * with Approve and Reject buttons. Nothing leaves the machine until Approve is pressed, and
 * an approved action runs exactly once. The list refreshes every five seconds.
 */
export function PendingActions() {
  const [actions, setActions] = useState<PendingAction[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const refresh = useCallback(() => {
    invoke<unknown>("pending_actions")
      .then((reply) => setActions(parsePending(reply)))
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
      {actions.length === 0 && <p className="mt-2 text-sm text-zinc-600">Nothing is waiting for you.</p>}
      <ul className="mt-2 flex flex-col gap-3">
        {actions.map((action) => (
          <li key={action.id} className="rounded-lg border border-zinc-300 p-3">
            <p className="text-xs text-zinc-600">{action.heading}</p>
            {action.title && <h3 className="font-semibold">{action.title}</h3>}
            {action.detail && <p className="text-xs text-zinc-600">{action.detail}</p>}
            {action.body && (
              <pre className="mt-1 max-h-40 overflow-auto text-sm whitespace-pre-wrap">{action.body}</pre>
            )}
            <div className="mt-2 flex gap-2">
              <button
                type="button"
                disabled={busy !== null}
                onClick={() => decide(action.id, true)}
                className="cursor-pointer rounded-md bg-zinc-900 px-3 py-1.5 text-sm text-white hover:bg-zinc-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busy === action.id ? "Working…" : action.approveLabel}
              </button>
              <button
                type="button"
                disabled={busy !== null}
                onClick={() => decide(action.id, false)}
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
