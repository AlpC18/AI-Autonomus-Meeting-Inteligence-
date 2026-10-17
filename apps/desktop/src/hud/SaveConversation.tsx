// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { save } from "@tauri-apps/plugin-dialog";
import { displaySpeaker } from "./speakers";
import { BLOCK_MS, timeOfDay, transcriptBlocks } from "./TranscriptFeed";
import { timeOf } from "./Timeline";
import type { Topic, TranscriptSegment } from "./transcriptStream";
import { t } from "../i18n";

/** The conversation as Markdown: the timeline, then two-minute blocks of who said what. */
export function conversationMarkdown(
  title: string,
  segments: readonly TranscriptSegment[],
  captions: Readonly<Record<string, string>>,
  topics: readonly Topic[],
  savedAt: Date,
): string {
  const lines = [`# ${title}`, "", `${savedAt.toLocaleDateString()} ${timeOfDay(savedAt.getTime())}`, ""];
  if (topics.length > 0) {
    lines.push(`## ${t("Timeline")}`, "", ...topics.map((topic) => `- ${timeOf(topic.at)} ${topic.title}`), "");
  }
  lines.push(`## ${t("Conversation")}`, "");
  for (const block of transcriptBlocks(segments, captions)) {
    lines.push(`### ${timeOfDay(block.from)} – ${timeOfDay(block.from + BLOCK_MS)}`, "");
    for (const paragraph of block.paragraphs) {
      lines.push(`**${displaySpeaker(paragraph.speaker)}:** ${paragraph.text}`);
      for (const caption of paragraph.captions) lines.push(`> ${caption}`);
      lines.push("");
    }
  }
  return lines.join("\n");
}

/** A safe default file name: the title without characters file systems reject. */
const fileName = (title: string, at: Date) =>
  `${at.toISOString().slice(0, 10)} ${title.replace(/[\\/:*?"<>|]/g, "-").trim() || "Meeting"}.md`;

interface SaveConversationProps {
  title: string;
  segments: readonly TranscriptSegment[];
  captions: Readonly<Record<string, string>>;
  topics: readonly Topic[];
}

/** "Save conversation": writes the live transcript so far to a Markdown file the user picks. */
export function SaveConversation({ title, segments, captions, topics }: SaveConversationProps) {
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null);

  const run = async () => {
    const now = new Date();
    const path = await save({ title: t("Save conversation"), defaultPath: fileName(title, now), filters: [{ name: "Markdown", extensions: ["md", "txt"] }] });
    if (path === null) return;
    await invoke("save_transcript", { path, text: conversationMarkdown(title, segments, captions, topics, now) });
    setMessage({ text: t("Saved."), error: false });
  };

  return (
    <>
      <button
        type="button"
        disabled={segments.length === 0}
        onClick={() => void run().catch((cause: unknown) => setMessage({ text: String(cause), error: true }))}
        className="cursor-pointer rounded-md border border-zinc-400 px-3 py-1.5 text-sm hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {t("Save conversation")}
      </button>
      {message && (
        <span role={message.error ? "alert" : "status"} className={`text-xs ${message.error ? "text-red-700" : "text-zinc-600"}`}>
          {message.text}
        </span>
      )}
    </>
  );
}
