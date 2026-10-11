// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

/** A live statement whose figures differ from the most recent record. */
export interface FactCheckAlert {
  /** What was just said. */
  statement: string;
  /** Who said it. */
  speaker: string;
  /** The conflicting figures as spoken now, e.g. ["$50,000"]. */
  claimed: string[];
  /** The figures on record, e.g. ["$35,000"]. */
  recorded: string[];
  /** The earlier statement the record comes from. */
  recordText: string;
  recordSpeaker: string;
  /** When the earlier statement was made. Invalid if the engine sent a bad date. */
  recordSpokenAt: Date;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

/**
 * Extracts the alert from one raw WebSocket message.
 *
 * Returns `null` for anything that is not a well-formed fact-check message
 * (invalid JSON, another message type, missing or mistyped fields), so
 * malformed input from the socket never reaches the UI.
 */
export function parseAlertMessage(raw: unknown): FactCheckAlert | null {
  if (typeof raw !== "string") return null;
  let message: unknown;
  try {
    message = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!isRecord(message) || message.type !== "fact_check") return null;
  const alert = message.alert;
  if (
    !isRecord(alert) ||
    typeof alert.statement !== "string" ||
    typeof alert.speaker !== "string" ||
    !isStringArray(alert.claimed) ||
    !isStringArray(alert.recorded) ||
    typeof alert.record_text !== "string" ||
    typeof alert.record_speaker !== "string" ||
    typeof alert.record_spoken_at !== "string"
  ) {
    return null;
  }
  return {
    statement: alert.statement,
    speaker: alert.speaker,
    claimed: alert.claimed,
    recorded: alert.recorded,
    recordText: alert.record_text,
    recordSpeaker: alert.record_speaker,
    recordSpokenAt: new Date(alert.record_spoken_at),
  };
}
