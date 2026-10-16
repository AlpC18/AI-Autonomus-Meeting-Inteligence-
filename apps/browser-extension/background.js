// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

// Clicking the toolbar button starts or stops capturing the current tab.
// The audio itself is handled in an offscreen document (service workers
// cannot hold media streams); closing that document ends the capture.

const OFFSCREEN = "offscreen.html";

const BADGES = {
  on: ["ON", "#15803d", "Continuum hears this tab. Click to stop."],
  waiting: ["…", "#a16207", "Waiting for the Continuum app (is it running with browser tab audio on?)."],
  busy: ["!", "#b91c1c", "Continuum is already capturing another tab."],
  off: ["", "#000000", "Continuum: capture this tab's audio"],
};

async function show(state) {
  const [text, color, title] = BADGES[state] ?? BADGES.off;
  await chrome.action.setBadgeText({ text });
  await chrome.action.setBadgeBackgroundColor({ color });
  await chrome.action.setTitle({ title });
}

async function capturing() {
  const contexts = await chrome.runtime.getContexts({ contextTypes: ["OFFSCREEN_DOCUMENT"] });
  return contexts.length > 0;
}

async function stop() {
  if (await capturing()) await chrome.offscreen.closeDocument();
  await show("off");
}

/** Starts or stops capturing `tab` (what clicking the toolbar button does). */
async function toggle(tab) {
  if (await capturing()) {
    await stop();
    return;
  }
  const streamId = await chrome.tabCapture.getMediaStreamId({ targetTabId: tab.id });
  await chrome.offscreen.createDocument({
    url: OFFSCREEN,
    reasons: ["USER_MEDIA"],
    justification: "Sends the meeting tab's audio to the Continuum app on this computer.",
  });
  await show("waiting");
  await chrome.runtime.sendMessage({ target: "offscreen", type: "start", streamId });
}

chrome.action.onClicked.addListener(toggle);

chrome.runtime.onMessage.addListener((message) => {
  if (message?.target !== "background") return;
  if (message.type === "ended") void stop();
  else void show(message.type);
});
