// @vitest-environment jsdom
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { clearMocks, mockIPC } from "@tauri-apps/api/mocks";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { SettingsPanel } from "./SettingsPanel";

afterEach(() => {
  cleanup();
  clearMocks();
});

describe("SettingsPanel", () => {
  it("shows the diagnostics report to copy when the clipboard is unavailable", async () => {
    mockIPC((cmd) => {
      if (cmd === "get_settings") return { fields: [], values: {}, secretsSet: [] };
      if (cmd === "diagnostics") return "Recall desktop 0.1.0 (macos aarch64)\n\n# Recall diagnostics";
      throw new Error(`unexpected command ${cmd}`);
    });
    render(<SettingsPanel />);

    fireEvent.click(await screen.findByRole("button", { name: "Copy diagnostics" }));

    const report = (await screen.findByLabelText("Diagnostics")) as HTMLTextAreaElement;
    expect(report.value).toContain("# Recall diagnostics");
    expect(screen.getByRole("status").textContent).toContain("Copy the diagnostics below");
  });

  const field = (key: string, label: string, kind: string, options: string[] = []) => ({ key, label, group: "General", kind, options, help: "" });
  const view = {
    fields: [
      field("RECALL_WHISPER_MODEL", "Speech model", "text"),
      field("RECALL_WS_PORT", "Port", "number"),
      field("RECALL_LANGUAGE", "Language", "choice", ["en", "tr"]),
      field("RECALL_SCREEN_FACT_CHECK", "Fact-check shared slides", "toggle", ["0"]),
      field("GROQ_API_KEY", "Groq key", "secret"),
      field("GITHUB_TOKEN", "GitHub token", "secret"),
      field("GOOGLE_REFRESH_TOKEN", "Google", "secret"),
    ],
    values: { RECALL_WHISPER_MODEL: "small", RECALL_LANGUAGE: "en" },
    secretsSet: ["GITHUB_TOKEN"],
  };

  it("saves edited values, new secrets and removed secrets", async () => {
    const calls: Array<[string, unknown]> = [];
    mockIPC((cmd, args) => {
      calls.push([cmd, args]);
      if (cmd === "get_settings") return view;
      if (cmd === "save_settings") return [];
      throw new Error(`unexpected command ${cmd}`);
    });
    render(<SettingsPanel />);

    fireEvent.change(await screen.findByLabelText("Speech model"), { target: { value: "large-v3" } });
    fireEvent.change(screen.getByLabelText("Language"), { target: { value: "tr" } });
    fireEvent.click(screen.getByLabelText("Fact-check shared slides"));
    fireEvent.change(screen.getByLabelText("Groq key"), { target: { value: " gsk_new " } });
    expect((screen.getByLabelText("GitHub token") as HTMLInputElement).placeholder).toBe("Saved in Keychain — type to replace");
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    expect((screen.getByLabelText("Google") as HTMLInputElement).placeholder).toBe("Not set");
    expect((screen.getByRole("button", { name: "Connect Google…" }) as HTMLButtonElement).disabled).toBe(true);

    fireEvent.click(screen.getByRole("button", { name: "Save and restart engine" }));

    await waitFor(() => expect(screen.getByRole("status").textContent).toContain("Saved. The engine restarted"));
    const [, saved] = calls.find(([cmd]) => cmd === "save_settings")!;
    expect(saved).toEqual({
      values: { RECALL_WHISPER_MODEL: "large-v3", RECALL_LANGUAGE: "tr", RECALL_SCREEN_FACT_CHECK: "1" },
      secrets: { GROQ_API_KEY: "gsk_new", GITHUB_TOKEN: "" },
    });
  });

  it("lists configuration problems and connection results", async () => {
    mockIPC((cmd) => {
      if (cmd === "get_settings") return view;
      if (cmd === "save_settings") return ["GROQ_API_KEY is set but RECALL_LLM is not"];
      if (cmd === "check_connections") return [{ service: "GitHub", ok: true, detail: "signed in as ana" }, { service: "Groq", ok: false, detail: "401" }];
      throw new Error(`unexpected command ${cmd}`);
    });
    render(<SettingsPanel />);

    fireEvent.click(await screen.findByRole("button", { name: "Test connections" }));
    await waitFor(() => expect(screen.getByRole("status").textContent).toBe("✓ GitHub: signed in as ana✗ Groq: 401"));

    fireEvent.click(screen.getByRole("button", { name: "Save and restart engine" }));
    await waitFor(() => expect(screen.getByRole("status").textContent).toBe("GROQ_API_KEY is set but RECALL_LLM is not"));
  });

  it("shows why settings could not be loaded", async () => {
    mockIPC(() => {
      throw new Error("engine folder missing");
    });
    render(<SettingsPanel />);
    expect((await screen.findByText(/engine folder missing/)).textContent).toContain("engine folder missing");
  });
});
