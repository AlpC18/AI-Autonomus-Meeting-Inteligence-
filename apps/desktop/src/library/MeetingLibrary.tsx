// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { convertFileSrc, invoke } from "@tauri-apps/api/core";
import {
  filterLines,
  formatTime,
  parseMeeting,
  parseMeetingList,
  parseSearchHits,
  type Meeting,
  type MeetingFile,
  type SearchHit,
} from "./library";

const BUTTON =
  "cursor-pointer rounded-md border border-zinc-400 px-3 py-1.5 text-sm hover:bg-zinc-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900 disabled:cursor-not-allowed disabled:opacity-50";

/**
 * Past meetings: a searchable list, and the selected meeting's transcript.
 *
 * Search looks for the words in every meeting's transcript. When a meeting
 * has a recording, each line's time plays the recording from that moment.
 * "Summarize with AI" sends the transcript to the AI provider the user
 * configured and saves the summary in the notes.
 */
export function MeetingLibrary() {
  const [meetings, setMeetings] = useState<MeetingFile[]>([]);
  const [meeting, setMeeting] = useState<Meeting | null>(null);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  // Where to start playing once a newly opened recording has loaded.
  const pendingSeek = useRef<number | null>(null);

  const refresh = useCallback(() => {
    invoke<unknown>("library_list")
      .then((reply) => setMeetings(parseMeetingList(reply)))
      .catch((cause: unknown) => setNotice(String(cause)));
  }, []);

  useEffect(refresh, [refresh]);

  const open = (path: string, seekTo?: number) => {
    setNotice(null);
    invoke<unknown>("library_show", { path })
      .then((reply) => {
        const opened = parseMeeting(reply);
        setMeeting(opened);
        setFilter("");
        pendingSeek.current = seekTo ?? null;
        if (!opened) setNotice("That meeting could not be read.");
      })
      .catch((cause: unknown) => setNotice(String(cause)));
  };

  const play = (seconds: number) => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = seconds;
    void audio.play().catch(() => setNotice("The recording could not be played."));
  };

  const search = (event: FormEvent) => {
    event.preventDefault();
    if (!query.trim()) {
      setHits(null);
      return;
    }
    invoke<unknown>("library_search", { query })
      .then((reply) => setHits(parseSearchHits(reply)))
      .catch((cause: unknown) => setNotice(String(cause)));
  };

  const summarize = () => {
    if (!meeting) return;
    setBusy(true);
    setNotice("Summarizing… the transcript is being sent to your configured AI provider.");
    invoke<unknown>("library_summarize", { path: meeting.path })
      .then((reply) => {
        setMeeting(parseMeeting(reply));
        setNotice("Summary saved in the notes.");
        refresh();
      })
      .catch((cause: unknown) => setNotice(String(cause)))
      .finally(() => setBusy(false));
  };

  const shown = meeting ? filterLines(meeting.lines, filter) : [];

  return (
    <section aria-label="Past meetings" className="mt-4 grid gap-4 md:grid-cols-[16rem_1fr]">
      <div>
        <form onSubmit={search} role="search" className="flex gap-2">
          <input
            aria-label="Search all meetings"
            value={query}
            maxLength={200}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search all meetings"
            className="min-w-0 flex-1 rounded-md border border-zinc-300 p-1.5 text-sm"
          />
          <button type="submit" className={BUTTON}>
            Search
          </button>
        </form>
        {hits !== null && (
          <ul aria-label="Search results" className="mt-2 flex flex-col gap-1 text-sm">
            {hits.length === 0 && <li className="text-zinc-600">No lines match.</li>}
            {hits.map((hit, index) => (
              <li key={`${hit.path}-${hit.time}-${index}`}>
                <button
                  type="button"
                  onClick={() => open(hit.path, hit.time)}
                  className="w-full cursor-pointer rounded p-1 text-left hover:bg-zinc-100"
                >
                  <span className="block text-xs text-zinc-600">
                    {hit.title} · {formatTime(hit.time)}
                  </span>
                  <strong>{hit.speaker}:</strong> {hit.text}
                </button>
              </li>
            ))}
          </ul>
        )}
        <h2 className="mt-4 text-sm font-semibold">Meetings</h2>
        {meetings.length === 0 && <p className="text-sm text-zinc-600">No meeting notes yet.</p>}
        <ul className="mt-1 flex flex-col gap-1 text-sm">
          {meetings.map((item) => (
            <li key={item.path}>
              <button
                type="button"
                aria-current={meeting?.path === item.path}
                onClick={() => open(item.path)}
                className="w-full cursor-pointer rounded p-1 text-left hover:bg-zinc-100 aria-[current=true]:bg-zinc-200"
              >
                {item.title}
                <span className="block text-xs text-zinc-600">
                  {new Date(item.modified).toLocaleString()}
                  {item.hasSummary ? " · summarized" : ""}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div>
        {notice && (
          <p role="status" className="mb-2 text-sm break-words text-zinc-700">
            {notice}
          </p>
        )}
        {!meeting && <p className="text-sm text-zinc-600">Choose a meeting to read it.</p>}
        {meeting && (
          <article>
            <h2 className="text-lg font-semibold">{meeting.title}</h2>
            {meeting.audio ? (
              <audio
                ref={audioRef}
                controls
                src={convertFileSrc(meeting.audio)}
                onLoadedMetadata={() => {
                  if (pendingSeek.current !== null) play(pendingSeek.current);
                  pendingSeek.current = null;
                }}
                className="mt-2 w-full"
              />
            ) : (
              <p className="mt-1 text-xs text-zinc-600">No recording is linked to this meeting.</p>
            )}
            <div className="mt-2 flex flex-wrap gap-2">
              <input
                aria-label="Filter this meeting"
                value={filter}
                onChange={(event) => setFilter(event.target.value)}
                placeholder="Filter lines"
                className="min-w-0 flex-1 rounded-md border border-zinc-300 p-1.5 text-sm"
              />
              <button type="button" disabled={busy} onClick={summarize} className={BUTTON}>
                {busy ? "Summarizing…" : meeting.summary ? "Summarize again" : "Summarize with AI"}
              </button>
            </div>
            {meeting.summary && (
              <pre className="mt-3 rounded-md bg-zinc-50 p-3 text-sm whitespace-pre-wrap">{meeting.summary}</pre>
            )}
            <ol className="mt-3 flex flex-col gap-1 text-sm">
              {shown.map((line, index) => (
                <li key={`${line.time}-${index}`} className={line.speaker === "Note" ? "border-l-4 border-amber-400 bg-amber-50 pl-2" : undefined}>
                  {meeting.audio ? (
                    <button
                      type="button"
                      onClick={() => play(line.time)}
                      aria-label={`Play from ${formatTime(line.time)}`}
                      className="mr-2 cursor-pointer font-mono text-xs text-blue-700 underline"
                    >
                      {formatTime(line.time)}
                    </button>
                  ) : (
                    <span className="mr-2 font-mono text-xs text-zinc-500">{formatTime(line.time)}</span>
                  )}
                  <strong>{line.speaker}:</strong> {line.text}
                </li>
              ))}
            </ol>
          </article>
        )}
      </div>
    </section>
  );
}
