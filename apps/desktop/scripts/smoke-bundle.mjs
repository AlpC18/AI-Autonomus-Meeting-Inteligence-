// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

// Starts the engine of an installed app the way the app does (engine.rs,
// `Bundle`): the bundled uv installs Python 3.12 and the locked environment
// into a fresh folder, then the engine is imported and its native libraries
// run (embeddings through onnxruntime, PDF reading, figure extraction).
//
// Usage: node scripts/smoke-bundle.mjs <engine-dir> <bundled-uv>

import { execFileSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [engineDir, uv] = process.argv.slice(2);
if (!engineDir || !uv) {
  console.error("Usage: node scripts/smoke-bundle.mjs <engine-dir> <bundled-uv>");
  process.exit(2);
}

const data = mkdtempSync(join(tmpdir(), "recall-smoke-"));
const env = {
  ...process.env,
  UV_PYTHON: "3.12",
  UV_PYTHON_PREFERENCE: "only-managed",
  UV_PROJECT_ENVIRONMENT: join(data, "venv"),
  UV_PYTHON_INSTALL_DIR: join(data, "python"),
  UV_CACHE_DIR: join(data, "cache"),
  PYTHONPYCACHEPREFIX: join(data, "pycache"),
  HF_HOME: join(data, "models"),
};

const check = `
import platform
import numpy as np
import pypdf
import recall.actions.server, recall.pipeline, recall.session
from recall.factcheck.figures import extract_figures
from recall.memory.embedder import load_embedder

assert [f.value for f in extract_figures("the budget is $35,000")] == [35000.0]
embed, dimensions = load_embedder()
vectors = embed(["the budget is 35k", "budget was thirty-five thousand"])
assert len(vectors) == 2 and len(vectors[0]) == dimensions
print("bundled engine OK on", platform.system(), platform.machine())
`;

// Same arguments as Bundle::run_args without a Hugging Face token (no PyTorch download).
execFileSync(uv, ["run", "--frozen", "--no-dev", "--extra", "claude", "--extra", "documents", "python", "-c", check], {
  cwd: engineDir,
  env,
  stdio: "inherit",
});
