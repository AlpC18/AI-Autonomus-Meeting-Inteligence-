// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

/** What a live hint is about. */
export type HintKind = "code" | "commitment" | "hesitation";

/** A live hint for the overlay: code a statement is about, or a risky promise. */
export interface Hint {
  kind: HintKind;
  title: string;
  body: string;
  /** File paths or other short lines, shown as a list. */
  details: string[];
}

const KINDS: readonly string[] = ["code", "commitment", "hesitation"];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/** Extracts the hint from one raw WebSocket message, or `null` for anything malformed. */
export function parseHintMessage(raw: unknown): Hint | null {
  if (typeof raw !== "string") return null;
  let message: unknown;
  try {
    message = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!isRecord(message) || message.type !== "hint" || !isRecord(message.hint)) return null;
  const { kind, title, body, details } = message.hint;
  if (typeof kind !== "string" || !KINDS.includes(kind) || typeof title !== "string" || typeof body !== "string") {
    return null;
  }
  const lines = Array.isArray(details) ? details.filter((line): line is string => typeof line === "string") : [];
  return { kind: kind as HintKind, title, body, details: lines.slice(0, 10) };
}
