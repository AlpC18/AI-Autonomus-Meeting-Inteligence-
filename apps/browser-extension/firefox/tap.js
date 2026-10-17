// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

// Runs in the meeting page itself (Firefox has no tab capture for extensions).
// Every audio track the call receives (the other participants) is mixed,
// averaged down to 16 kHz and posted as 100 ms blocks to relay.js, which
// forwards them only while the user has switched capture on for this tab.
(() => {
  const TARGET_RATE = 16000;
  const BLOCK = TARGET_RATE / 10;
  const TAG = "recall-call-audio";

  function downsampler(rate, emit) {
    let block = new Float32Array(BLOCK);
    let filled = 0;
    let sum = 0;
    let count = 0;
    let units = 0;
    return (samples) => {
      for (const sample of samples) {
        sum += sample;
        count += 1;
        units += TARGET_RATE;
        if (units >= rate) {
          units -= rate;
          block[filled++] = sum / count;
          sum = 0;
          count = 0;
          if (filled === BLOCK) {
            emit(block);
            block = new Float32Array(BLOCK);
            filled = 0;
          }
        }
      }
    };
  }

  let context = null;
  let mixer = null;
  const tapped = new Set();

  function tap(track) {
    if (track.kind !== "audio" || tapped.has(track.id)) return;
    tapped.add(track.id);
    if (!context) {
      context = new AudioContext();
      mixer = context.createScriptProcessor(4096, 1, 1);
      const feed = downsampler(context.sampleRate, (block) => window.postMessage({ type: TAG, samples: Array.from(block) }, "*"));
      mixer.onaudioprocess = (event) => feed(event.inputBuffer.getChannelData(0));
      mixer.connect(context.destination); // must be connected to run; it outputs silence
    }
    context.createMediaStreamSource(new MediaStream([track])).connect(mixer);
    track.addEventListener("ended", () => tapped.delete(track.id));
  }

  const Original = window.RTCPeerConnection;
  if (!Original) return;
  window.RTCPeerConnection = class extends Original {
    constructor(...args) {
      super(...args);
      this.addEventListener("track", (event) => tap(event.track));
    }
  };
})();
