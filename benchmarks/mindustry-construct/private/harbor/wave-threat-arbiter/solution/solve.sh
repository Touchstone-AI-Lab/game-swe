#!/usr/bin/env bash
set -euo pipefail

mkdir -p /workspace/mindustry/src

cp /solution/ThreatArbiter.java \
   /workspace/mindustry/src/ThreatArbiter.java

cp /solution/WaveThreatArbiterPlugin.java \
   /workspace/mindustry/src/WaveThreatArbiterPlugin.java

if [ -f /solution/plugin.hjson ]; then
    cp /solution/plugin.hjson /workspace/mindustry/plugin.hjson
fi
