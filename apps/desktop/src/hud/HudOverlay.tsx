// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { useEffect, useLayoutEffect, useRef } from "react";
import { LogicalPosition, LogicalSize } from "@tauri-apps/api/dpi";
import { currentMonitor, getCurrentWindow } from "@tauri-apps/api/window";
import { FactCheckCard } from "./FactCheckCard";
import { HintCard } from "./HintCard";
import { useTranscriptStream } from "./transcriptStream";

const WIDTH = 380;
const SCREEN_MARGIN = 16;
/** Leaves room for the macOS menu bar. */
const TOP_OFFSET = 44;
/** How long a card stays before it removes itself. */
const AUTO_DISMISS_MS = 30_000;

/**
 * Sizes the overlay window to its cards and pins it to the top-right corner.
 *
 * With nothing to show the window shrinks to one transparent pixel that lets
 * clicks through, instead of being hidden: macOS suspends the scripts of a
 * hidden window, which would stop it reconnecting to the engine.
 */
async function fitWindow(height: number): Promise<void> {
  const overlay = getCurrentWindow();
  if (height === 0) {
    await overlay.setIgnoreCursorEvents(true);
    await overlay.setSize(new LogicalSize(1, 1));
    return;
  }
  await overlay.setIgnoreCursorEvents(false);
  await overlay.setSize(new LogicalSize(WIDTH, Math.ceil(height)));
  const monitor = await currentMonitor();
  if (monitor) {
    const scale = monitor.scaleFactor;
    const right = (monitor.position.x + monitor.size.width) / scale;
    const top = monitor.position.y / scale;
    await overlay.setPosition(
      new LogicalPosition(right - WIDTH - SCREEN_MARGIN, top + TOP_OFFSET),
    );
  }
}

/**
 * Root of the floating overlay window.
 *
 * While there is nothing to show the window is a single click-through pixel,
 * so it never covers or intercepts clicks on other apps. When alerts arrive
 * it resizes itself to exactly fit the cards at the top-right of the screen,
 * above other windows, and shrinks back once every card is dismissed or has
 * timed out.
 */
export function HudOverlay() {
  const { alerts, dismissAlert, hints, dismissHint } = useTranscriptStream();
  const container = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const height = alerts.length + hints.length === 0 ? 0 : (container.current?.offsetHeight ?? 0);
    fitWindow(height).catch(reportError);
  }, [alerts, hints]);

  useEffect(() => {
    const newest = alerts[alerts.length - 1];
    if (!newest) return;
    const timer = window.setTimeout(() => dismissAlert(newest.id), AUTO_DISMISS_MS);
    return () => window.clearTimeout(timer);
  }, [alerts, dismissAlert]);

  useEffect(() => {
    const newest = hints[hints.length - 1];
    if (!newest) return;
    const timer = window.setTimeout(() => dismissHint(newest.id), AUTO_DISMISS_MS);
    return () => window.clearTimeout(timer);
  }, [hints, dismissHint]);

  return (
    // Fixed width: the cards are measured while the window is still one pixel
    // wide, and must not wrap to that width.
    <div ref={container} style={{ width: WIDTH }} className="flex flex-col gap-2 p-1">
      {alerts.map(({ id, alert }) => (
        <FactCheckCard key={id} alert={alert} onDismiss={() => dismissAlert(id)} />
      ))}
      {hints.map(({ id, hint }) => (
        <HintCard key={id} hint={hint} onDismiss={() => dismissHint(id)} />
      ))}
    </div>
  );
}
