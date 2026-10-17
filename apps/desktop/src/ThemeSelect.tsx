// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { useEffect, useState } from "react";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { applyTheme, storedTheme, THEMES, type Theme } from "./theme";
import { t } from "./i18n";

const THEME_NAMES: Record<Theme, string> = {
  system: "System appearance",
  light: "Light",
  dark: "Dark",
};

/** Matches the native title bar to the theme; the page is themed either way. */
function setWindowTheme(theme: "light" | "dark" | null): void {
  try {
    void getCurrentWindow()
      .setTheme(theme)
      .catch(() => {});
  } catch {
    // Outside the app window (tests): nothing to tell.
  }
}

/** Light, dark, or following the system; remembered on this machine. */
export function ThemeSelect() {
  const [theme, setTheme] = useState<Theme>(storedTheme);
  useEffect(() => applyTheme(theme, setWindowTheme), [theme]);

  return (
    <label className="flex items-center gap-2 text-xs text-zinc-600">
      <span className="sr-only">{t("Appearance")}</span>
      <select
        aria-label={t("Appearance")}
        value={theme}
        onChange={(event) => setTheme(event.target.value as Theme)}
        className="cursor-pointer rounded-md border border-zinc-200 py-1 pr-7 pl-2.5 text-xs"
      >
        {THEMES.map((name) => (
          <option key={name} value={name}>
            {t(THEME_NAMES[name])}
          </option>
        ))}
      </select>
    </label>
  );
}
