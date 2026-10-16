// @vitest-environment jsdom
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { clearMocks, mockIPC } from "@tauri-apps/api/mocks";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { MeetingLibrary } from "./MeetingLibrary";

afterEach(() => {
  cleanup();
  clearMocks();
});

const budget = {
  path: "/notes/budget.md",
  title: "Budget review",
  audio: null,
  summary: null,
  lines: [
    { time: 5, speaker: "Ana", text: "Budget is $35,000" },
    { time: 65, speaker: "Note", text: "Push back on December" },
  ],
};

function library(overrides: Record<string, (args: Record<string, unknown>) => unknown> = {}) {
  const calls: Array<[string, Record<string, unknown>]> = [];
  mockIPC((cmd, args) => {
    const payload = (args ?? {}) as Record<string, unknown>;
    calls.push([cmd, payload]);
    if (overrides[cmd]) return overrides[cmd](payload);
    if (cmd === "library_list") return [{ path: budget.path, title: budget.title, modified: "2026-10-01T10:00:00Z", has_summary: false }];
    if (cmd === "library_show") return budget;
    throw new Error(`unexpected command ${cmd}`);
  });
  render(<MeetingLibrary />);
  return calls;
}

describe("MeetingLibrary", () => {
  it("opens a meeting, filters its lines and summarizes it", async () => {
    const calls = library({ library_summarize: () => ({ ...budget, summary: "## Summary\nBudget agreed." }) });

    fireEvent.click(await screen.findByRole("button", { name: /Budget review/ }));
    const article = await screen.findByRole("article");
    expect(within(article).getByText("No recording is linked to this meeting.")).toBeTruthy();
    expect(article.textContent).toContain("1:05");

    fireEvent.change(screen.getByLabelText("Filter this meeting"), { target: { value: "december" } });
    expect(within(article).queryByText(/Budget is/)).toBeNull();
    expect(within(article).getByText(/Push back/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Summarize with AI" }));
    await waitFor(() => expect(screen.getByRole("status").textContent).toBe("Summary saved in the notes."));
    expect(article.textContent).toContain("Budget agreed.");
    expect(calls.filter(([cmd]) => cmd === "library_list")).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Summarize again" })).toBeTruthy();
  });

  it("searches every meeting and opens a hit", async () => {
    const calls = library({ library_search: () => [{ ...budget.lines[0], path: budget.path, title: budget.title }, { bad: true }] });
    await screen.findByRole("button", { name: /Budget review/ });

    fireEvent.change(screen.getByLabelText("Search all meetings"), { target: { value: "budget" } });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    const results = await screen.findByRole("list", { name: "Search results" });
    expect(within(results).getAllByRole("listitem")).toHaveLength(1);

    fireEvent.click(within(results).getByRole("button"));
    await screen.findByRole("article");
    expect(calls).toContainEqual(["library_show", { path: budget.path }]);

    fireEvent.change(screen.getByLabelText("Search all meetings"), { target: { value: " " } });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(screen.queryByRole("list", { name: "Search results" })).toBeNull();
  });

  it("says when nothing matches, a meeting is unreadable or the engine fails", async () => {
    library({ library_search: () => [], library_show: () => ({ nope: 1 }), library_summarize: () => Promise.reject("no AI provider") });
    fireEvent.change(await screen.findByLabelText("Search all meetings"), { target: { value: "zzz" } });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(await screen.findByText("No lines match.")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /Budget review/ }));
    expect(await screen.findByText("That meeting could not be read.")).toBeTruthy();
  });

  it("shows an empty library", async () => {
    library({ library_list: () => [] });
    expect(await screen.findByText("No meeting notes yet.")).toBeTruthy();
    expect(screen.getByText("Choose a meeting to read it.")).toBeTruthy();
  });
});
