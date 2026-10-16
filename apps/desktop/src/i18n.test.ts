// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { afterEach, describe, expect, it } from "vitest";
import settingsRs from "../src-tauri/src/settings.rs?raw";
import { setLanguage, t } from "./i18n";
import { TR } from "./i18n.tr";

const SOURCES: Record<string, string> = import.meta.glob(["./**/*.{ts,tsx}", "!./**/*.test.*", "!./i18n*"], {
  query: "?raw",
  import: "default",
  eager: true,
});

afterEach(() => setLanguage("en"));

/** Every English text the interface shows through `t`, plus the settings' labels, groups and help. */
function shownTexts(): string[] {
  const texts = Object.values(SOURCES).flatMap((source) =>
    [...source.matchAll(/\bt\("((?:[^"\\]|\\.)*)"/g)].map((match) => JSON.parse(`"${match[1]}"`) as string),
  );
  for (const block of settingsRs.matchAll(/\n {4}field\(([\s\S]*?)\n {4}\),/g)) {
    const literals = [...block[1].matchAll(/"((?:[^"\\]|\\.)*)"/g)].map((match) => JSON.parse(`"${match[1]}"`) as string);
    texts.push(literals[1], literals[2], literals[literals.length - 1]);
  }
  return texts;
}

describe("interface language", () => {
  it("translates and fills placeholders, falling back to English", () => {
    setLanguage("tr");
    expect(t("End meeting")).toBe("Toplantıyı bitir");
    expect(t("Added {name} ({count} passages)", { name: "fiyat.pdf", count: 3 })).toBe("fiyat.pdf eklendi (3 bölüm)");
    expect(t("Not a known text")).toBe("Not a known text");
    setLanguage("xx");
    expect(t("End meeting")).toBe("End meeting");
  });

  it("has a Turkish text for everything the interface and the settings show", () => {
    const shown = shownTexts();
    expect(shown.length).toBeGreaterThan(200); // the sources and settings were really read
    const missing = [...new Set(shown)].filter((text) => !(text in TR) && /[a-z]{3}/.test(text) && !text.startsWith("https://"));
    expect(missing).toEqual([]);
  });

  it("keeps every placeholder in the Turkish text", () => {
    const broken = Object.entries(TR).filter(([english, turkish]) => {
      const names = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((match) => match[1]).sort().join();
      return names(english) !== names(turkish);
    });
    expect(broken).toEqual([]);
  });
});
