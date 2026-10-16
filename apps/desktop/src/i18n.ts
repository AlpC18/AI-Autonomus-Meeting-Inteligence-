// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { TR } from "./i18n.tr";

/** Languages of the interface; the setting is `CONTINUUM_LANGUAGE`. */
export type Language = "en" | "tr";

const STORAGE_KEY = "continuum.language";

function stored(): Language {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "tr" ? "tr" : "en";
  } catch {
    return "en";
  }
}

let current: Language = typeof window === "undefined" ? "en" : stored();

/**
 * Uses `language` from now on and remembers it, so the overlay window (which
 * does not read the settings) follows. Unknown values mean English.
 */
export function setLanguage(language: string | undefined): void {
  current = language === "tr" ? "tr" : "en";
  try {
    window.localStorage.setItem(STORAGE_KEY, current);
  } catch {
    // Not remembered: the overlay stays in the previous language until restart.
  }
}

/** The interface language. */
export function language(): Language {
  return current;
}

/**
 * `text` (written in English) in the interface language, with `{name}`
 * placeholders filled from `values`. Untranslated text stays English.
 */
export function t(text: string, values?: Record<string, string | number>): string {
  const template = current === "tr" ? (TR[text] ?? text) : text;
  return values ? template.replace(/\{(\w+)\}/g, (match: string, key: string) => (key in values ? String(values[key]) : match)) : template;
}
