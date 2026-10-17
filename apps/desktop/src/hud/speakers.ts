// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { t } from "../i18n";

/** The label the engine uses for the microphone, the local user. */
export const ME = "me";
/** The label for system audio when voices are not told apart. */
export const OTHERS = "others";

/**
 * How a speaker label reads on screen: the engine's "Speaker 2" is
 * "Person 2", "me" is "You", "others" is "Others"; names the user gave are
 * shown as they are. The engine keeps its own labels (voice memory relies on them).
 */
export function displaySpeaker(label: string): string {
  const numbered = /^Speaker (\d+)$/.exec(label);
  if (numbered) return t("Person {n}", { n: numbered[1] });
  if (label === ME) return t("You");
  if (label === OTHERS) return t("Others");
  return label;
}

/** Text colours that stay readable in the light and the dark theme, one per person. */
const COLORS = ["text-teal-700", "text-violet-700", "text-amber-700", "text-sky-700", "text-rose-700", "text-lime-700"];

/** A stable colour for `label`: the same person keeps the same colour all meeting. */
export function speakerColor(label: string): string {
  if (label === ME) return "text-zinc-900";
  let hash = 0;
  for (const char of label) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return COLORS[hash % COLORS.length];
}
