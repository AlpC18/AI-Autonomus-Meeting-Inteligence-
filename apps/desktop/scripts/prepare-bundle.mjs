// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

// Prepares what release builds bundle next to the app: removes Python caches
// from the engine sources, then downloads the pinned uv binary for the target
// platform and checks it against the checksum published with the release.
// Runs on macOS, Windows and Linux (Node 22, and the `tar` every one of them ships).
//
// Usage: node scripts/prepare-bundle.mjs [target-triple]
// The target is, in order: the argument, TAURI_ENV_TARGET_TRIPLE (set by
// `tauri build --target ...`), or this machine's.

import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { chmodSync, copyFileSync, mkdirSync, mkdtempSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const UV_VERSION = "0.12.15";
const desktop = join(dirname(fileURLToPath(import.meta.url)), "..");
const engineSources = join(desktop, "..", "..", "engine", "src");

function removePycache(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const path = join(dir, entry.name);
    if (entry.name === "__pycache__") rmSync(path, { recursive: true, force: true });
    else removePycache(path);
  }
}

function hostTarget() {
  const info = execFileSync("rustc", ["-vV"], { encoding: "utf8" });
  const host = info.match(/^host: (.+)$/m);
  if (!host) throw new Error("rustc -vV did not report a host target");
  return host[1].trim();
}

function findFile(dir, name) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isFile() && entry.name === name) return path;
    if (entry.isDirectory()) {
      const found = findFile(path, name);
      if (found) return found;
    }
  }
  return null;
}

async function download(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Download failed (${response.status}): ${url}`);
  return Buffer.from(await response.arrayBuffer());
}

function installedVersion(path) {
  try {
    statSync(path);
    return execFileSync(path, ["--version"], { encoding: "utf8" });
  } catch {
    return "";
  }
}

async function fetchUv(target) {
  const windows = target.includes("windows");
  const out = join(desktop, "src-tauri", "binaries", `uv-${target}${windows ? ".exe" : ""}`);
  // A binary for another platform cannot be run to check its version, so it is fetched again.
  if (target === hostTarget() && installedVersion(out).includes(` ${UV_VERSION}`)) {
    console.log(`uv ${UV_VERSION} for ${target} already present`);
    return;
  }

  const archive = `uv-${target}.${windows ? "zip" : "tar.gz"}`;
  const url = `https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/${archive}`;
  const [data, checksum] = await Promise.all([download(url), download(`${url}.sha256`)]);
  const expected = checksum.toString("utf8").split(/\s+/)[0];
  const actual = createHash("sha256").update(data).digest("hex");
  if (expected !== actual) throw new Error(`Checksum mismatch for ${archive}`);

  const work = mkdtempSync(join(tmpdir(), "recall-uv-"));
  try {
    writeFileSync(join(work, archive), data);
    // bsdtar (macOS, Windows 10+) reads zip and tar.gz; GNU tar only gets tar.gz here.
    execFileSync("tar", ["-xf", archive], { cwd: work });
    const binary = findFile(work, windows ? "uv.exe" : "uv");
    if (!binary) throw new Error(`${archive} has no uv binary`);
    mkdirSync(dirname(out), { recursive: true });
    copyFileSync(binary, out);
    chmodSync(out, 0o755);
  } finally {
    rmSync(work, { recursive: true, force: true });
  }
  console.log(`Installed uv ${UV_VERSION} to ${out}`);
}

removePycache(engineSources);
await fetchUv(process.argv[2] || process.env.TAURI_ENV_TARGET_TRIPLE || hostTarget());
