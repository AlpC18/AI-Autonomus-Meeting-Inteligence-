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
});
