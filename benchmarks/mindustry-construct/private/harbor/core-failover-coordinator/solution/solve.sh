#!/usr/bin/env bash
set -euo pipefail
mkdir -p /workspace/mindustry/src
cp /solution/CoreFailoverCoordinator.java /workspace/mindustry/src/CoreFailoverCoordinator.java
cp /solution/CoreFailoverCoordinatorPlugin.java /workspace/mindustry/src/CoreFailoverCoordinatorPlugin.java
cp /solution/plugin.hjson /workspace/mindustry/plugin.hjson
cp /solution/build-reference.sh /workspace/mindustry/build-reference.sh
