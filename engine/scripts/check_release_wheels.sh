#!/bin/sh
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.
#
# Checks that every locked dependency installs as a ready-made wheel on each
# platform release builds ship for: users have no compilers, so a package that
# would build from source breaks the app's first start on that platform.
# macOS 14 is the app's minimum (tauri.conf.json).
set -eu
cd "$(dirname "$0")/.."
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
uv export --frozen --no-dev --all-extras --no-emit-project --no-hashes -q > "$work/requirements.txt"
for platform in aarch64-apple-darwin x86_64-apple-darwin x86_64-pc-windows-msvc x86_64-unknown-linux-gnu; do
  MACOSX_DEPLOYMENT_TARGET=14.0 uv pip compile "$work/requirements.txt" --python-platform "$platform" \
    --python-version 3.12 --only-binary :all: --no-deps -q -o "$work/$platform.txt"
  echo "$platform: all wheels"
done
