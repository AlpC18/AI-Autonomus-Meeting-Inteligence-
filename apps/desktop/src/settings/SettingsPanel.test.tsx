// @vitest-environment jsdom
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { clearMocks, mockIPC } from "@tauri-apps/api/mocks";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
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
      if (cmd === "diagnostics") return "Continuum desktop 0.1.0 (macos aarch64)\n\n# Continuum diagnostics";
      throw new Error(`unexpected command ${cmd}`);
    });
    render(<SettingsPanel />);

    fireEvent.click(await screen.findByRole("button", { name: "Copy diagnostics" }));

    const report = (await screen.findByLabelText("Diagnostics")) as HTMLTextAreaElement;
    expect(report.value).toContain("# Continuum diagnostics");
    expect(screen.getByRole("status").textContent).toContain("Copy the diagnostics below");
  });
});
