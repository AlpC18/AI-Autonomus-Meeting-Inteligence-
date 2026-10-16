// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

/** A past meeting in the list. */
export interface MeetingFile {
  path: string;
  title: string;
  /** ISO time the notes were last changed. */
  modified: string;
  hasSummary: boolean;
}

/** One transcript line of a past meeting. */
export interface MeetingLine {
  /** Seconds from the start of the recording or meeting. */
  time: number;
  speaker: string;
  text: string;
}

/** A past meeting opened in the viewer. */
export interface Meeting {
  path: string;
  title: string;
  /** Recording to play back, or `null` when there is none. */
  audio: string | null;
  /** The AI summary in Markdown, or `null`. */
  summary: string | null;
  lines: MeetingLine[];
}

/** A search hit: a line and the meeting it is in. */
export interface SearchHit extends MeetingLine {
  path: string;
  title: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isLine(value: unknown): value is MeetingLine {
  return (
    isRecord(value) &&
    typeof value.time === "number" &&
    typeof value.speaker === "string" &&
    typeof value.text === "string"
  );
}

/** Keeps the well-formed meetings of a `library_list` reply. */
export function parseMeetingList(reply: unknown): MeetingFile[] {
  if (!Array.isArray(reply)) return [];
  return reply.flatMap((item): MeetingFile[] =>
    isRecord(item) &&
    typeof item.path === "string" &&
    typeof item.title === "string" &&
    typeof item.modified === "string"
      ? [{ path: item.path, title: item.title, modified: item.modified, hasSummary: item.has_summary === true }]
      : [],
  );
}

/** Reads a `library_show` reply, or returns `null` if it is malformed. */
export function parseMeeting(reply: unknown): Meeting | null {
  if (!isRecord(reply) || typeof reply.path !== "string" || typeof reply.title !== "string") return null;
  if (!Array.isArray(reply.lines)) return null;
  return {
    path: reply.path,
    title: reply.title,
    audio: typeof reply.audio === "string" ? reply.audio : null,
    summary: typeof reply.summary === "string" ? reply.summary : null,
    lines: reply.lines.filter(isLine),
  };
}

/** Keeps the well-formed hits of a `library_search` reply. */
export function parseSearchHits(reply: unknown): SearchHit[] {
  if (!Array.isArray(reply)) return [];
  return reply.flatMap((item): SearchHit[] =>
    isLine(item) && isRecord(item) && typeof item.path === "string" && typeof item.title === "string"
      ? [{ path: item.path, title: item.title, time: item.time, speaker: item.speaker, text: item.text }]
      : [],
  );
}

/** Formats seconds as `H:MM:SS` or `M:SS`. */
export function formatTime(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor((whole % 3600) / 60);
  const secs = String(whole % 60).padStart(2, "0");
  return hours > 0 ? `${hours}:${String(minutes).padStart(2, "0")}:${secs}` : `${minutes}:${secs}`;
}

/** Lines of `meeting` that contain `filter` (any case), or all lines when it is empty. */
export function filterLines(lines: readonly MeetingLine[], filter: string): MeetingLine[] {
  const needle = filter.trim().toLowerCase();
  if (!needle) return [...lines];
  return lines.filter(
    (line) => line.text.toLowerCase().includes(needle) || line.speaker.toLowerCase().includes(needle),
  );
}
