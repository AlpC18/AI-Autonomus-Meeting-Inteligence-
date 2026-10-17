// @vitest-environment jsdom
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { clearMocks, mockIPC } from "@tauri-apps/api/mocks";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FakeSocket } from "./hud/fakeSocket.test.helper";

const overlay = vi.hoisted(() => ({
  setSize: vi.fn().mockResolvedValue(undefined),
  setPosition: vi.fn().mockResolvedValue(undefined),
  setIgnoreCursorEvents: vi.fn().mockResolvedValue(undefined),
}));
vi.mock("@tauri-apps/plugin-updater", () => ({ check: () => Promise.resolve(null) }));
vi.mock("@tauri-apps/plugin-process", () => ({ relaunch: vi.fn() }));
vi.mock("@tauri-apps/api/window", () => ({
  getCurrentWindow: () => overlay,
  currentMonitor: () => Promise.resolve({ scaleFactor: 2, position: { x: 0, y: 0 }, size: { width: 3024, height: 1964 } }),
}));

import App from "./App";
import { HudOverlay } from "./hud/HudOverlay";

const settings = { fields: [], values: { RECALL_LANGUAGE: "en" }, secretsSet: [] };

beforeEach(() => {
  FakeSocket.all = [];
  vi.stubGlobal("WebSocket", FakeSocket);
  window.localStorage.clear();
});

afterEach(() => {
  cleanup();
  clearMocks();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

function backend(appInfo: () => unknown = () => ({ name: "recall-desktop", version: "0.1.0" })) {
  mockIPC((cmd) => {
    if (cmd === "app_info") return appInfo();
    if (cmd === "get_settings") return settings;
    if (cmd === "pending_actions") return [];
    if (cmd === "library_list") return [];
    throw new Error(`unexpected command ${cmd}`);
  });
}

describe("App", () => {
  it("opens the first-run checklist, then moves between views", async () => {
    backend();
    render(<App />);

    expect(await screen.findByText("recall-desktop v0.1.0")).toBeTruthy();
    await waitFor(() => expect(screen.getByRole("button", { name: "Get started" }).getAttribute("aria-pressed")).toBe("true"));

    fireEvent.click(screen.getByRole("button", { name: "Past meetings" }));
    expect(await screen.findByText("No meeting notes yet.")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Settings" }));
    expect(await screen.findByRole("form", { name: "Settings" })).toBeTruthy();
  });

  it("keeps the live transcript flowing from the engine", async () => {
    window.localStorage.setItem("recall.setupHidden", "1");
    backend();
    render(<App />);
    await screen.findByText("recall-desktop v0.1.0");

    const socket = FakeSocket.all[0];
    act(() => {
      socket.open();
      socket.push({ type: "segment", segment: { source: "system", start: 0, end: 1, text: "Budget is $35,000", speaker: "Speaker 1", words: [] } });
    });
    expect(screen.getByText(/Budget is \$35,000/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Get started" })).toBeNull();
  });

  it("says when the desktop backend cannot be reached", async () => {
    backend(() => {
      throw new Error("no backend");
    });
    render(<App />);
    expect((await screen.findByRole("alert")).textContent).toContain("Could not reach the desktop backend");
  });
});

describe("HudOverlay", () => {
  it("grows to fit a fact check, then shrinks to a click-through pixel when it times out", async () => {
    vi.useFakeTimers();
    // WebKit has reportError; jsdom does not. A failed resize must be reported, not thrown.
    const reportError = vi.fn();
    vi.stubGlobal("reportError", reportError);
    // jsdom does no layout; give the cards a height to measure.
    const height = vi.spyOn(HTMLElement.prototype, "offsetHeight", "get").mockReturnValue(240);
    render(<HudOverlay />);
    const socket = FakeSocket.all[0];
    await act(async () => socket.open());
    expect(overlay.setSize).toHaveBeenLastCalledWith(expect.objectContaining({ width: 1, height: 1 }));

    await act(async () => {
      socket.push({
        type: "fact_check",
        alert: { statement: "It is $50,000", speaker: "Ana", claimed: ["$50,000"], recorded: ["$35,000"], record_text: "Budget is $35,000", record_speaker: "Ben", record_spoken_at: "2026-10-01T10:00:00Z" },
      });
      socket.push({ type: "hint", hint: { kind: "code", title: "Paddle", body: "Used in 3 files", details: [] } });
    });
    expect(screen.getByRole("button", { name: "Dismiss fact check" })).toBeTruthy();
    expect(overlay.setIgnoreCursorEvents).toHaveBeenLastCalledWith(false);
    expect(overlay.setSize).toHaveBeenLastCalledWith(expect.objectContaining({ width: 380, height: 240 }));
    expect(overlay.setPosition).toHaveBeenLastCalledWith(expect.objectContaining({ x: 3024 / 2 - 380 - 16, y: 44 }));

    await act(async () => vi.advanceTimersByTime(30_000));
    expect(screen.queryAllByRole("status")).toEqual([]);
    expect(overlay.setIgnoreCursorEvents).toHaveBeenLastCalledWith(true);
    expect(overlay.setSize).toHaveBeenLastCalledWith(expect.objectContaining({ width: 1, height: 1 }));
    expect(reportError).not.toHaveBeenCalled();
    height.mockRestore();
  });
});
