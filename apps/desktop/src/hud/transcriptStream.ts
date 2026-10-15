// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { useCallback, useEffect, useRef, useState } from "react";
import { parseAlertMessage, type FactCheckAlert } from "./factCheck";

/** One transcribed word, timed in seconds since the engine started capturing. */
export interface TranscriptWord {
  text: string;
  start: number;
  end: number;
  speaker: string | null;
}

/** A run of speech from one audio source, as sent by the engine. */
export interface TranscriptSegment {
  /** Capture stream: "mic" or "system". */
  source: string;
  start: number;
  end: number;
  text: string;
  words: TranscriptWord[];
  /** Dominant speaker of the segment. */
  speaker: string;
}

/** Whether the HUD currently has a live connection to the engine. */
export type StreamStatus = "connecting" | "open" | "closed";

/** A fact-check alert with a local id, so it can be listed and dismissed. */
export interface ShownAlert {
  id: number;
  alert: FactCheckAlert;
}

/** Live engine state returned by {@link useTranscriptStream}. */
export interface TranscriptStream {
  status: StreamStatus;
  /** Most recent segments, oldest first, capped at {@link MAX_SEGMENTS}. */
  segments: readonly TranscriptSegment[];
  /** Undismissed fact-check alerts, oldest first, capped at {@link MAX_ALERTS}. */
  alerts: readonly ShownAlert[];
  /** Removes one alert by its id. Unknown ids are ignored. */
  dismissAlert: (id: number) => void;
  /**
   * Sends a message to the engine (a typed note or a speaker rename).
   * Returns `false` when the engine is not connected, so nothing was sent.
   */
  send: (message: EngineCommand) => boolean;
  /** Title of the meeting being recorded (from the calendar, or "Meeting"). */
  meetingTitle: string;
  /** Answers received, keyed by question id. */
  answers: Readonly<Record<string, Answer>>;
  /** The summary of the meeting that ended last, if any. */
  lastSummary: MeetingSummaryEvent | null;
}

/** What the desktop app can ask the engine to do during a meeting. */
export type EngineCommand =
  | { type: "note"; text: string }
  | { type: "rename_speaker"; from: string; to: string }
  | { type: "ask"; id: string; question: string }
  | { type: "end_meeting" };

/** A statement from memory that an answer cites. */
export interface AnswerSource {
  number: number;
  speaker: string;
  text: string;
  spokenAt: Date;
  disputed: boolean;
}

/** The engine's reply to a question; `error` explains why there is no answer. */
export interface Answer {
  id: string;
  text: string;
  sources: AnswerSource[];
  error: string | null;
}

/** What the engine reports when a meeting ends. */
export interface MeetingSummaryEvent {
  markdown: string | null;
  queued: number;
  errors: string[];
  error: string | null;
}

/** Meeting-level events from the engine, other than transcript and alerts. */
export type EngineEvent =
  | { type: "answer"; answer: Answer }
  | { type: "summary"; summary: MeetingSummaryEvent }
  | { type: "meeting_started"; title: string }
  | { type: "meeting_ended"; reason: string };

/** The engine's confirmation that a speaker is now shown under another name. */
export interface Renamed {
  from: string;
  to: string;
}

/** Default address of the engine's transcript WebSocket. */
export const ENGINE_STREAM_URL = "ws://127.0.0.1:8765";

/** How many segments the HUD keeps; older ones are dropped. */
export const MAX_SEGMENTS = 200;

/** How many fact-check alerts are shown at once; older ones are dropped. */
export const MAX_ALERTS = 3;

const RECONNECT_DELAY_MS = 2000;

let nextAlertId = 0;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isWord(value: unknown): value is TranscriptWord {
  return (
    isRecord(value) &&
    typeof value.text === "string" &&
    typeof value.start === "number" &&
    typeof value.end === "number" &&
    (typeof value.speaker === "string" || value.speaker === null)
  );
}

/**
 * Extracts the segment from one raw WebSocket message.
 *
 * Returns `null` for anything that is not a well-formed segment message
 * (invalid JSON, another message type, missing fields), so malformed input
 * from the socket never reaches the UI.
 */
export function parseSegmentMessage(raw: unknown): TranscriptSegment | null {
  if (typeof raw !== "string") return null;
  let message: unknown;
  try {
    message = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!isRecord(message) || message.type !== "segment") return null;
  const segment = message.segment;
  if (
    !isRecord(segment) ||
    typeof segment.source !== "string" ||
    typeof segment.start !== "number" ||
    typeof segment.end !== "number" ||
    typeof segment.text !== "string" ||
    typeof segment.speaker !== "string" ||
    !Array.isArray(segment.words) ||
    !segment.words.every(isWord)
  ) {
    return null;
  }
  return {
    source: segment.source,
    start: segment.start,
    end: segment.end,
    text: segment.text,
    speaker: segment.speaker,
    words: segment.words,
  };
}

/** Extracts a speaker rename from one raw WebSocket message, or `null`. */
export function parseRenamedMessage(raw: unknown): Renamed | null {
  if (typeof raw !== "string") return null;
  let message: unknown;
  try {
    message = JSON.parse(raw);
  } catch {
    return null;
  }
  if (
    !isRecord(message) ||
    message.type !== "renamed" ||
    typeof message.from !== "string" ||
    typeof message.to !== "string"
  ) {
    return null;
  }
  return { from: message.from, to: message.to };
}

function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

/** Extracts an answer, summary or meeting change from one raw WebSocket message, or `null`. */
export function parseEngineEvent(raw: unknown): EngineEvent | null {
  if (typeof raw !== "string") return null;
  let message: unknown;
  try {
    message = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!isRecord(message)) return null;
  if (message.type === "answer" && typeof message.id === "string") {
    const sources = Array.isArray(message.sources)
      ? message.sources.flatMap((source): AnswerSource[] =>
          isRecord(source) &&
          typeof source.number === "number" &&
          typeof source.speaker === "string" &&
          typeof source.text === "string" &&
          typeof source.spoken_at === "string"
            ? [{ number: source.number, speaker: source.speaker, text: source.text, spokenAt: new Date(source.spoken_at), disputed: source.disputed === true }]
            : [],
        )
      : [];
    return {
      type: "answer",
      answer: {
        id: message.id,
        text: typeof message.text === "string" ? message.text : "",
        sources,
        error: typeof message.error === "string" ? message.error : null,
      },
    };
  }
  if (message.type === "summary") {
    return {
      type: "summary",
      summary: {
        markdown: typeof message.markdown === "string" ? message.markdown : null,
        queued: typeof message.queued === "number" ? message.queued : 0,
        errors: strings(message.errors),
        error: typeof message.error === "string" ? message.error : null,
      },
    };
  }
  if (message.type === "meeting_started" && typeof message.title === "string") {
    return { type: "meeting_started", title: message.title };
  }
  if (message.type === "meeting_ended" && typeof message.reason === "string") {
    return { type: "meeting_ended", reason: message.reason };
  }
  return null;
}

/** Returns `segment` with speaker `from` shown as `to`, in the segment and its words. */
export function renameInSegment(segment: TranscriptSegment, { from, to }: Renamed): TranscriptSegment {
  const swap = (speaker: string) => (speaker === from ? to : speaker);
  return {
    ...segment,
    speaker: swap(segment.speaker),
    words: segment.words.map((word) =>
      word.speaker === null ? word : { ...word, speaker: swap(word.speaker) },
    ),
  };
}

/**
 * Subscribes to the engine's live transcript and fact-check alerts.
 *
 * Connects to `url`, collects incoming segments and alerts, and reconnects every two
 * seconds while the engine is unreachable, so the HUD recovers on its own when
 * the engine starts late or restarts. The socket is closed on unmount.
 */
export function useTranscriptStream(url: string = ENGINE_STREAM_URL): TranscriptStream {
  const [status, setStatus] = useState<StreamStatus>("connecting");
  const [segments, setSegments] = useState<readonly TranscriptSegment[]>([]);
  const [alerts, setAlerts] = useState<readonly ShownAlert[]>([]);
  const socketRef = useRef<WebSocket | null>(null);
  const [meetingTitle, setMeetingTitle] = useState("Meeting");
  const [answers, setAnswers] = useState<Readonly<Record<string, Answer>>>({});
  const [lastSummary, setLastSummary] = useState<MeetingSummaryEvent | null>(null);
  const send = useCallback((message: EngineCommand) => {
    const socket = socketRef.current;
    if (socket === null || socket.readyState !== WebSocket.OPEN) return false;
    socket.send(JSON.stringify(message));
    return true;
  }, []);
  const dismissAlert = useCallback((id: number) => {
    setAlerts((current) => current.filter((shown) => shown.id !== id));
  }, []);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let retry: number | undefined;
    let stopped = false;

    const open = () => {
      setStatus("connecting");
      socket = new WebSocket(url);
      socketRef.current = socket;
      socket.onopen = () => setStatus("open");
      socket.onmessage = (event: MessageEvent<unknown>) => {
        const segment = parseSegmentMessage(event.data);
        if (segment) {
          setSegments((current) => [...current, segment].slice(-MAX_SEGMENTS));
          return;
        }
        const alert = parseAlertMessage(event.data);
        if (alert) {
          const shown = { id: nextAlertId++, alert };
          setAlerts((current) => [...current, shown].slice(-MAX_ALERTS));
          return;
        }
        const renamed = parseRenamedMessage(event.data);
        if (renamed) {
          setSegments((current) => current.map((segment) => renameInSegment(segment, renamed)));
          return;
        }
        const engineEvent = parseEngineEvent(event.data);
        if (engineEvent?.type === "answer") {
          const { answer } = engineEvent;
          setAnswers((current) => ({ ...current, [answer.id]: answer }));
        } else if (engineEvent?.type === "summary") {
          setLastSummary(engineEvent.summary);
        } else if (engineEvent?.type === "meeting_started") {
          // A new meeting starts with an empty transcript.
          setMeetingTitle(engineEvent.title);
          setSegments([]);
        }
      };
      socket.onclose = () => {
        if (stopped) return;
        setStatus("closed");
        retry = window.setTimeout(open, RECONNECT_DELAY_MS);
      };
    };
    open();

    return () => {
      stopped = true;
      window.clearTimeout(retry);
      socketRef.current = null;
      socket?.close();
    };
  }, [url]);

  return { status, segments, alerts, dismissAlert, send, meetingTitle, answers, lastSummary };
}
