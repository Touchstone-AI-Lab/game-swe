#!/usr/bin/env bash
set -euo pipefail

mkdir -p /workspace/mindustry/src

cp /solution/BuildQuotaAuditorPlugin.java /workspace/mindustry/src/BuildQuotaAuditorPlugin.java
cp /solution/BuildQuotaEngine.java /workspace/mindustry/src/BuildQuotaEngine.java

if [ -f /solution/plugin.hjson ]; then
    cp /solution/plugin.hjson /workspace/mindustry/plugin.hjson
fi
