#!/usr/bin/env bash
set -euo pipefail
mkdir -p /workspace/mindustry/src
cp /solution/LogicLinkRegistry.java /workspace/mindustry/src/LogicLinkRegistry.java
cp /solution/LogicLinkRegistryPlugin.java /workspace/mindustry/src/LogicLinkRegistryPlugin.java
cp /solution/plugin.hjson /workspace/mindustry/plugin.hjson
cp /solution/build-reference.sh /workspace/mindustry/build-reference.sh
