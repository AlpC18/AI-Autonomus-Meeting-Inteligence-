// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { PendingActions } from "./actions/PendingActions";
import { AskPanel, MeetingBar, SpeakerNamer, TranscriptFeed, useTranscriptStream } from "./hud";
import { MeetingLibrary } from "./library/MeetingLibrary";
import { Notepad } from "./notes/Notepad";
import { parseSettings, type SettingsView } from "./settings/settings";
import { SettingsPanel } from "./settings/SettingsPanel";
import { UpdateBanner } from "./update/UpdateBanner";
import { SetupChecklist } from "./setup/SetupChecklist";
import { setupComplete, setupSteps } from "./setup/setup";
import { setLanguage, t } from "./i18n";

type View = "setup" | "live" | "meetings" | "settings";
const VIEW_NAMES: Record<View, string> = {
  setup: "Get started",
  live: "Live meeting",
  meetings: "Past meetings",
  settings: "Settings",
};
const SETUP_HIDDEN_KEY = "continuum.setupHidden";

function setupHidden(): boolean {
  try {
    return window.localStorage.getItem(SETUP_HIDDEN_KEY) === "1";
  } catch {
    return false;
  }
}

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
  const [view, setView] = useState<View>("live");
  const [settings, setSettings] = useState<SettingsView | null>(null);
  const [heardSpeech, setHeardSpeech] = useState(false);
  const [hidden, setHidden] = useState(setupHidden);
  if (!heardSpeech && stream.segments.some((segment) => segment.source !== "note")) setHeardSpeech(true);
  if (settings) setLanguage(settings.values.CONTINUUM_LANGUAGE);
  const steps = settings ? setupSteps(settings, heardSpeech) : null;
  const showSetup = !hidden && steps !== null && !setupComplete(steps);

  // Settings are re-read on every view change and after a checklist step is saved.
  const [settingsVersion, setSettingsVersion] = useState(0);
  useEffect(() => {
    invoke<unknown>("get_settings")
      .then((reply) => setSettings(parseSettings(reply)))
      .catch(() => setSettings(null));
  }, [view, settingsVersion]);

  // The checklist opens by itself on first run, until it is complete or hidden.
  const [opened, setOpened] = useState(false);
  if (!opened && showSetup) {
    setOpened(true);
    setView("setup");
  }

  const hideSetup = () => {
    try {
      window.localStorage.setItem(SETUP_HIDDEN_KEY, "1");
    } catch {
      // Not remembered: the checklist comes back next launch.
    }
    setHidden(true);
    setView("live");
  };

  useEffect(() => {
    invoke<AppInfo>("app_info")
      .then(setInfo)
      .catch((cause: unknown) => setError(String(cause)));
  }, []);

  return (
    <main className="p-4">
      <h1 className="text-2xl font-bold">Continuum</h1>
      {error && <p role="alert">{t("Could not reach the desktop backend: {error}", { error })}</p>}
      <UpdateBanner />
      {info && (
        <p>
          {info.name} v{info.version}
        </p>
      )}
      <nav aria-label={t("Views")} className="mt-3 flex gap-2">
        {(showSetup || view === "setup" ? (["setup", "live", "meetings", "settings"] as const) : (["live", "meetings", "settings"] as const)).map((name) => (
          <button
            key={name}
            type="button"
            aria-pressed={view === name}
            onClick={() => setView(name)}
            className="cursor-pointer rounded-md border border-zinc-400 px-3 py-1.5 text-sm hover:bg-zinc-100 aria-pressed:bg-zinc-900 aria-pressed:text-white"
          >
            {t(VIEW_NAMES[name])}
          </button>
        ))}
      </nav>
      {/* The live view stays mounted so the transcript keeps flowing while browsing. */}
      <div hidden={view !== "live"}>
        <MeetingBar title={stream.meetingTitle} connected={connected} send={stream.send} lastSummary={stream.lastSummary} brief={stream.brief} liveItems={stream.liveItems} lastTalkTime={stream.lastTalkTime} project={stream.project} projectError={stream.projectError} lastReport={stream.lastReport} lastImport={stream.lastImport} />
        <TranscriptFeed status={stream.status} segments={stream.segments} captions={stream.captions} />
        <SpeakerNamer segments={stream.segments} connected={connected} send={stream.send} />
        <Notepad connected={connected} send={stream.send} />
        <AskPanel connected={connected} send={stream.send} answers={stream.answers} />
      </div>
      {view === "setup" && steps && settings && (
        <SetupChecklist
          steps={steps}
          settings={settings}
          saved={() => setSettingsVersion((version) => version + 1)}
          openSettings={() => setView("settings")}
          dismiss={hideSetup}
        />
      )}
      {view === "meetings" && <MeetingLibrary />}
      {view === "settings" && <SettingsPanel />}
      <PendingActions />
    </main>
  );
}
