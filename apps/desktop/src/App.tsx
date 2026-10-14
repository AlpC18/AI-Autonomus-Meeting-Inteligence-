// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { PendingActions } from "./actions/PendingActions";
import { SpeakerNamer, TranscriptFeed, useTranscriptStream } from "./hud";
import { Notepad } from "./notes/Notepad";

/** Build identity returned by the Rust `app_info` command. */
interface AppInfo {
  /** Cargo package name of the desktop crate. */
  name: string;
  /** Semantic version of the desktop crate. */
  version: string;
}

/**
 * Root shell window. Shows the running build so it is obvious the webview and
 * the Rust backend are connected, then the live transcript, speaker names,
 * notes and proposed actions.
 * If the backend call fails, the error text is shown instead of a blank screen.
 */
export default function App() {
  const [info, setInfo] = useState<AppInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  // One connection to the engine, shared by the transcript, notes and names.
  const stream = useTranscriptStream();
  const connected = stream.status === "open";

  useEffect(() => {
    invoke<AppInfo>("app_info")
      .then(setInfo)
      .catch((cause: unknown) => setError(String(cause)));
  }, []);

  return (
    <main className="p-4">
      <h1 className="text-2xl font-bold">Continuum</h1>
      {error && <p role="alert">Could not reach the desktop backend: {error}</p>}
      {info && (
        <p>
          {info.name} v{info.version}
        </p>
      )}
      <TranscriptFeed status={stream.status} segments={stream.segments} />
      <SpeakerNamer segments={stream.segments} connected={connected} send={stream.send} />
      <Notepad connected={connected} send={stream.send} />
      <PendingActions />
    </main>
  );
}
