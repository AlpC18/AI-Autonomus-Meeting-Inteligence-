#!/bin/sh
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.
#
# Downloads the pinned uv binary that release builds bundle to run the engine,
# and checks it against the checksum published with the release.
# Usage: scripts/fetch-uv.sh [target-triple]   (default: this machine's)
set -eu

UV_VERSION="0.12.15"
TARGET="${1:-$(rustc -vV | sed -n 's/^host: //p')}"
DEST="$(cd "$(dirname "$0")/.." && pwd)/src-tauri/binaries"
OUT="$DEST/uv-$TARGET"

if [ -x "$OUT" ] && "$OUT" --version | grep -q " $UV_VERSION"; then
  echo "uv $UV_VERSION for $TARGET already present"
  exit 0
fi

ARCHIVE="uv-$TARGET.tar.gz"
URL="https://github.com/astral-sh/uv/releases/download/$UV_VERSION/$ARCHIVE"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

curl --fail --location --silent --show-error -o "$WORK/$ARCHIVE" "$URL"
curl --fail --location --silent --show-error -o "$WORK/$ARCHIVE.sha256" "$URL.sha256"
EXPECTED="$(cut -d ' ' -f 1 "$WORK/$ARCHIVE.sha256")"
ACTUAL="$(shasum -a 256 "$WORK/$ARCHIVE" | cut -d ' ' -f 1)"
if [ "$EXPECTED" != "$ACTUAL" ]; then
  echo "Checksum mismatch for $ARCHIVE" >&2
  exit 1
fi

tar -xzf "$WORK/$ARCHIVE" -C "$WORK"
mkdir -p "$DEST"
install -m 0755 "$WORK/uv-$TARGET/uv" "$OUT"
echo "Installed uv $UV_VERSION to $OUT"
