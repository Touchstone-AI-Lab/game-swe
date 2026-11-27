#!/usr/bin/env bash
set -euo pipefail
mkdir -p /workspace/mindustry/src
cp /solution/LayoutReconciler.java /workspace/mindustry/src/LayoutReconciler.java
cp /solution/BlueprintReconcilerPlugin.java /workspace/mindustry/src/BlueprintReconcilerPlugin.java
cp /solution/plugin.hjson /workspace/mindustry/plugin.hjson
cp /solution/build-reference.sh /workspace/mindustry/build-reference.sh
