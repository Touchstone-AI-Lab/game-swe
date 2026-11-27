#!/usr/bin/env bash
set -euo pipefail

mkdir -p /workspace/mindustry/src

cp /solution/PowerGridControllerPlugin.java \
   /workspace/mindustry/src/PowerGridControllerPlugin.java

cp /solution/GridController.java \
   /workspace/mindustry/src/GridController.java

if [ -f /solution/plugin.hjson ]; then
    cp /solution/plugin.hjson /workspace/mindustry/plugin.hjson
fi
