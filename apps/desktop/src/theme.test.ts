// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.
// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";
import { applyTheme, resolveTheme, storedTheme, THEME_KEY } from "./theme";

function systemPrefersDark(dark: boolean) {
  const listeners: Array<() => void> = [];
  const query = {
    matches: dark,
    addEventListener: (_: string, listener: () => void) => listeners.push(listener),
    removeEventListener: vi.fn(),
  };
  vi.stubGlobal("matchMedia", () => query);
  return {
    change(next: boolean) {
      query.matches = next;
      listeners.forEach((listener) => listener());
    },
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  window.localStorage.clear();
  delete document.documentElement.dataset.theme;
});

describe("theme", () => {
  it("follows the system until the user picks one", () => {
    expect(storedTheme()).toBe("system");
    window.localStorage.setItem(THEME_KEY, "dark");
    expect(storedTheme()).toBe("dark");
    window.localStorage.setItem(THEME_KEY, "purple");
    expect(storedTheme()).toBe("system");
  });

  it("resolves the system choice from the operating system", () => {
    systemPrefersDark(true);
    expect(resolveTheme("system")).toBe("dark");
    expect(resolveTheme("light")).toBe("light");
    systemPrefersDark(false);
    expect(resolveTheme("system")).toBe("light");
  });

  it("applies and remembers a choice, and tells the window title bar", () => {
    systemPrefersDark(false);
    const setWindowTheme = vi.fn();
    applyTheme("dark", setWindowTheme);
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(document.documentElement.style.colorScheme).toBe("dark");
    expect(window.localStorage.getItem(THEME_KEY)).toBe("dark");
    expect(setWindowTheme).toHaveBeenCalledWith("dark");
    applyTheme("system", setWindowTheme);
    expect(setWindowTheme).toHaveBeenLastCalledWith(null);
  });

  it("switches with the system while set to follow it", () => {
    const system = systemPrefersDark(false);
    const stop = applyTheme("system", () => {});
    expect(document.documentElement.dataset.theme).toBe("light");
    system.change(true);
    expect(document.documentElement.dataset.theme).toBe("dark");
    stop();
  });
});
