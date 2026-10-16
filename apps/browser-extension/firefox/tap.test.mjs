// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

// Run with: node --test apps/browser-extension/firefox/tap.test.mjs
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

function page() {
  const posted = [];
  const processors = [];
  class FakePeerConnection {
    constructor() {
      this.listeners = {};
    }
    addEventListener(type, listener) {
      (this.listeners[type] ??= []).push(listener);
    }
    receive(track) {
      for (const listener of this.listeners.track ?? []) listener({ track });
    }
  }
  class AudioContext {
    sampleRate = 48000;
    destination = {};
    createScriptProcessor() {
      const processor = { connect() {} };
      processors.push(processor);
      return processor;
    }
    createMediaStreamSource() {
      return { connect() {} };
    }
  }
  const window = { RTCPeerConnection: FakePeerConnection, postMessage: (message) => posted.push(message) };
  const context = vm.createContext({ window, AudioContext, MediaStream: class {}, Float32Array, Array, Set });
  vm.runInContext(readFileSync(new URL("./tap.js", import.meta.url), "utf8"), context);
  return { window, posted, processors };
}

test("the call's incoming audio becomes 100 ms blocks at 16 kHz", () => {
  const { window, posted, processors } = page();
  const call = new window.RTCPeerConnection();
  call.receive({ kind: "video", id: "v" });
  assert.equal(processors.length, 0);
  call.receive({ kind: "audio", id: "a", addEventListener() {} });
  call.receive({ kind: "audio", id: "a", addEventListener() {} }); // the same track once
  assert.equal(processors.length, 1);

  const second = new Float32Array(48000).fill(0.25);
  for (let i = 0; i < second.length; i += 4096) {
    processors[0].onaudioprocess({ inputBuffer: { getChannelData: () => second.subarray(i, i + 4096) } });
  }
  assert.equal(posted.length, 10);
  assert.ok(posted.every((message) => message.type === "continuum-call-audio" && message.samples.length === 1600));
  assert.ok(Math.abs(posted[0].samples[0] - 0.25) < 1e-6);
});
