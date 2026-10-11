// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { useEffect, useState } from "react";

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

/** Live transcript state returned by {@link useTranscriptStream}. */
export interface TranscriptStream {
  status: StreamStatus;
  /** Most recent segments, oldest first, capped at {@link MAX_SEGMENTS}. */
  segments: readonly TranscriptSegment[];
}

/** Default address of the engine's transcript WebSocket. */
export const ENGINE_STREAM_URL = "ws://127.0.0.1:8765";

/** How many segments the HUD keeps; older ones are dropped. */
export const MAX_SEGMENTS = 200;

const RECONNECT_DELAY_MS = 2000;

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

/**
 * Subscribes to the engine's live transcript.
 *
 * Connects to `url`, appends each incoming segment, and reconnects every two
 * seconds while the engine is unreachable, so the HUD recovers on its own when
 * the engine starts late or restarts. The socket is closed on unmount.
 */
export function useTranscriptStream(url: string = ENGINE_STREAM_URL): TranscriptStream {
  const [status, setStatus] = useState<StreamStatus>("connecting");
  const [segments, setSegments] = useState<readonly TranscriptSegment[]>([]);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let retry: number | undefined;
    let stopped = false;

    const open = () => {
      setStatus("connecting");
      socket = new WebSocket(url);
      socket.onopen = () => setStatus("open");
      socket.onmessage = (event: MessageEvent<unknown>) => {
        const segment = parseSegmentMessage(event.data);
        if (segment) {
          setSegments((current) => [...current, segment].slice(-MAX_SEGMENTS));
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
      socket?.close();
    };
  }, [url]);

  return { status, segments };
}
