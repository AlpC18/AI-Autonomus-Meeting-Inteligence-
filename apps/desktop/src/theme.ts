// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

/** What the user chose; "system" follows the operating system's appearance. */
export type Theme = "system" | "light" | "dark";

export const THEME_KEY = "recall.theme";
export const THEMES: readonly Theme[] = ["system", "light", "dark"];

/** Sets the native title bar; `null` lets it follow the system. */
export type SetWindowTheme = (theme: "light" | "dark" | null) => void;

const DARK_QUERY = "(prefers-color-scheme: dark)";

/** The remembered choice, or "system" when there is none (or storage is unavailable). */
export function storedTheme(): Theme {
  try {
    const value = window.localStorage.getItem(THEME_KEY);
    return value === "light" || value === "dark" ? value : "system";
  } catch {
    return "system";
  }
}

export function resolveTheme(theme: Theme): "light" | "dark" {
  if (theme !== "system") return theme;
  return window.matchMedia?.(DARK_QUERY).matches ? "dark" : "light";
}

function paint(theme: Theme): void {
  const resolved = resolveTheme(theme);
  document.documentElement.dataset.theme = resolved;
  document.documentElement.style.colorScheme = resolved;
}

/**
 * Shows `theme` now, remembers it, and tells the native window. While set to
 * "system", follows appearance changes; returns a function that stops that.
 */
export function applyTheme(theme: Theme, setWindowTheme: SetWindowTheme): () => void {
  paint(theme);
  try {
    if (theme === "system") window.localStorage.removeItem(THEME_KEY);
    else window.localStorage.setItem(THEME_KEY, theme);
  } catch {
    // Not remembered: the next launch follows the system.
  }
  setWindowTheme(theme === "system" ? null : theme);
  if (theme !== "system" || !window.matchMedia) return () => {};
  const query = window.matchMedia(DARK_QUERY);
  const follow = () => paint("system");
  query.addEventListener("change", follow);
  return () => query.removeEventListener("change", follow);
}
