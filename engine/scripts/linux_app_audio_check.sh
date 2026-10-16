#!/bin/sh
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.
#
# Hearing only the meeting app on real Linux audio, in a container:
#   docker run --rm -v "$PWD":/engine:ro debian:bookworm sh /engine/scripts/linux_app_audio_check.sh
# (run from engine/). A "zoom" and a "spotify" play different tones through
# PulseAudio at the same time; the engine must record only zoom's.
set -eu
apt-get update -qq >/dev/null
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq pulseaudio pulseaudio-utils sox python3-numpy >/dev/null
pulseaudio --version
pulseaudio -D --exit-idle-time=-1 --system=false --disallow-exit -n \
  --load=module-null-sink --load=module-native-protocol-unix
sleep 1
# application.process.binary is the executable's name, so copies of paplay play as "zoom" and "spotify".
cp "$(command -v paplay)" /usr/local/bin/zoom
cp "$(command -v paplay)" /usr/local/bin/spotify
sox -n -r 44100 -c 2 -b 16 /tmp/440.wav synth 30 sine 440 vol 0.5
sox -n -r 44100 -c 2 -b 16 /tmp/1000.wav synth 30 sine 1000 vol 0.9
zoom /tmp/440.wav &
spotify /tmp/1000.wav &
sleep 1
pactl list short sink-inputs
cd /engine && PYTHONPATH=src python3 scripts/linux_app_audio_check.py
