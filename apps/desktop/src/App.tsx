// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { TranscriptFeed } from "./hud";

/** Build identity returned by the Rust `app_info` command. */
interface AppInfo {
  /** Cargo package name of the desktop crate. */
  name: string;
  /** Semantic version of the desktop crate. */
  version: string;
}

/**
 * Root shell window. Shows the running build so it is obvious the webview and
 * the Rust backend are connected; feature views (HUD, notes) mount here later.
 * If the backend call fails, the error text is shown instead of a blank screen.
 */
export default function App() {
  const [info, setInfo] = useState<AppInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    invoke<AppInfo>("app_info")
      .then(setInfo)
      .catch((cause: unknown) => setError(String(cause)));
  }, []);

  return (
    <main>
      <h1>Continuum</h1>
      {error && <p role="alert">Could not reach the desktop backend: {error}</p>}
      {info && (
        <p>
          {info.name} v{info.version}
        </p>
      )}
      <TranscriptFeed />
    </main>
  );
}
