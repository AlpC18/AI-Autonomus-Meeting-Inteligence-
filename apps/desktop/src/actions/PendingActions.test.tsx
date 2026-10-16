// @vitest-environment jsdom
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { clearMocks, mockIPC } from "@tauri-apps/api/mocks";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { PendingActions } from "./PendingActions";

const NOTION = {
  id: "a1",
  kind: "notion_page",
  payload: { title: "Budget review", body: "## Summary\nAgreed." },
};

afterEach(() => {
  cleanup();
  clearMocks();
});

describe("PendingActions", () => {
  it("shows a proposal in full and approves it exactly as shown", async () => {
    const decisions: unknown[] = [];
    let pending = [NOTION, { id: "x", kind: "unknown_kind", payload: {} }];
    mockIPC((cmd, args) => {
      if (cmd === "pending_actions") return pending;
      if (cmd === "decide_action") {
        decisions.push(args);
        pending = [];
        return [{ status: "done", result: "https://www.notion.so/Budget-abc" }];
      }
      throw new Error(`unexpected command ${cmd}`);
    });

    render(<PendingActions />);

    expect(await screen.findByText("Budget review")).toBeTruthy();
    expect(screen.getByText(/Notion page under your configured parent page/)).toBeTruthy();
    expect(screen.getAllByRole("listitem")).toHaveLength(1); // the unknown kind is not offered
    fireEvent.click(screen.getByRole("button", { name: "Approve and create" }));

    expect(await screen.findByText("Done: https://www.notion.so/Budget-abc")).toBeTruthy();
    expect(decisions).toEqual([{ id: "a1", approve: true }]);
    expect(await screen.findByText("Nothing is waiting for you.")).toBeTruthy();
  });

  it("shows a GitLab issue with its project and labels", async () => {
    mockIPC((cmd) => {
      if (cmd === "pending_actions") {
        return [
          {
            id: "g1",
            kind: "gitlab_issue",
            payload: { project: "acme/web", title: "Ship the API", body: "From the meeting.", labels: ["backend"] },
          },
        ];
      }
      throw new Error(`unexpected command ${cmd}`);
    });

    render(<PendingActions />);

    expect(await screen.findByText("Ship the API")).toBeTruthy();
    expect(screen.getByText("GitLab issue in acme/web")).toBeTruthy();
    expect(screen.getByText("Labels: backend")).toBeTruthy();
  });

  it("rejects without sending anything", async () => {
    const decisions: unknown[] = [];
    mockIPC((cmd, args) => {
      if (cmd === "pending_actions") return decisions.length ? [] : [NOTION];
      decisions.push(args);
      return [{ status: "rejected" }];
    });

    render(<PendingActions />);
    fireEvent.click(await screen.findByRole("button", { name: "Reject" }));

    expect(await screen.findByText("Rejected. Nothing was sent.")).toBeTruthy();
    expect(decisions).toEqual([{ id: "a1", approve: false }]);
  });

  it("shows every kind of proposal with where it goes", async () => {
    mockIPC((cmd) => {
      if (cmd === "pending_actions") {
        return [
          { id: "1", kind: "github_issue", payload: { repo: "acme/web", title: "Fix login", labels: ["bug", 3] } },
          { id: "2", kind: "jira_issue", payload: { project: "WEB", summary: "Ship API", labels: ["q4"] } },
          { id: "3", kind: "slack_message", payload: { text: "Budget agreed" } },
          { id: "4", kind: "calendar_deadline", payload: { title: "Report", due: "2026-11-30" } },
          { id: "5", kind: "email_recap", payload: { subject: "Recap", to: ["ana@example.com", 7], body: "Hi" } },
          { id: "6", kind: "email_recap", payload: { subject: "Nobody", to: [] } },
          { id: "7", kind: "github_issue", payload: { repo: "acme/web" } },
        ];
      }
      throw new Error(`unexpected command ${cmd}`);
    });

    render(<PendingActions />);

    expect(await screen.findByText("GitHub issue in acme/web")).toBeTruthy();
    expect(screen.getByText("Labels: bug")).toBeTruthy();
    expect(screen.getByText("Jira task in project WEB")).toBeTruthy();
    expect(screen.getByText("Slack message to your configured channel")).toBeTruthy();
    expect(screen.getByText("Due: 2026-11-30 (all day)")).toBeTruthy();
    expect(screen.getByText("To: ana@example.com")).toBeTruthy();
    expect(screen.getAllByRole("listitem")).toHaveLength(5); // no recipient, no title: not offered
  });

  it("says when proposals cannot be loaded or a decision fails", async () => {
    let fail = true;
    mockIPC((cmd) => {
      if (cmd === "pending_actions") {
        if (fail) throw new Error("engine stopped");
        return [NOTION];
      }
      return [{ status: "failed" }];
    });

    const { unmount } = render(<PendingActions />);
    expect((await screen.findByRole("status")).textContent).toContain("Could not load proposed actions");
    unmount();

    fail = false;
    render(<PendingActions />);
    fireEvent.click(await screen.findByRole("button", { name: "Approve and create" }));
    expect(await screen.findByText("Failed: no details given")).toBeTruthy();
  });
});
