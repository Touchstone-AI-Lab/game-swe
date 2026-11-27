#!/usr/bin/env bash
set -euo pipefail
mkdir -p /workspace/mindustry/src
cp /solution/CommandRateLimiter.java /workspace/mindustry/src/CommandRateLimiter.java
cp /solution/CommandRateLimiterPlugin.java /workspace/mindustry/src/CommandRateLimiterPlugin.java
cp /solution/plugin.hjson /workspace/mindustry/plugin.hjson
cp /solution/build-reference.sh /workspace/mindustry/build-reference.sh
