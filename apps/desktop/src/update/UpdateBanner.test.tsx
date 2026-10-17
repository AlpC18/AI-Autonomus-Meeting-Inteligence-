// @vitest-environment jsdom
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const updater = vi.hoisted(() => ({ check: vi.fn(), relaunch: vi.fn() }));
vi.mock("@tauri-apps/plugin-updater", () => ({ check: updater.check }));
vi.mock("@tauri-apps/plugin-process", () => ({ relaunch: updater.relaunch }));

import { UpdateBanner } from "./UpdateBanner";

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe("UpdateBanner", () => {
  it("offers nothing when there is no release or the check fails", async () => {
    updater.check.mockRejectedValue(new Error("offline"));
    const { container } = render(<UpdateBanner />);
    await waitFor(() => expect(updater.check).toHaveBeenCalled());
    expect(container.innerHTML).toBe("");
  });

  it("installs a newer release only when clicked, then restarts", async () => {
    const downloadAndInstall = vi.fn().mockResolvedValue(undefined);
    updater.check.mockResolvedValue({ version: "0.2.0", downloadAndInstall });
    render(<UpdateBanner />);

    expect((await screen.findByRole("status")).textContent).toContain("Recall 0.2.0 is available.");
    expect(downloadAndInstall).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Install and restart" }));
    await waitFor(() => expect(updater.relaunch).toHaveBeenCalled());
  });

  it("says why an update failed and lets the user retry", async () => {
    updater.check.mockResolvedValue({ version: "0.2.0", downloadAndInstall: vi.fn().mockRejectedValue("bad signature") });
    render(<UpdateBanner />);
    fireEvent.click(await screen.findByRole("button", { name: "Install and restart" }));
    expect((await screen.findByText(/The update failed/)).textContent).toContain("bad signature");
    expect((screen.getByRole("button", { name: "Install and restart" }) as HTMLButtonElement).disabled).toBe(false);
    expect(updater.relaunch).not.toHaveBeenCalled();
  });
});
