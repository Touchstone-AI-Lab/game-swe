#!/usr/bin/env bash
set -euo pipefail

mkdir -p /workspace/mindustry/src

cp /solution/TransactionalCoreRouterPlugin.java \
   /workspace/mindustry/src/TransactionalCoreRouterPlugin.java

cp /solution/TransferEngine.java \
   /workspace/mindustry/src/TransferEngine.java

if [ -f /solution/plugin.hjson ]; then
    cp /solution/plugin.hjson /workspace/mindustry/plugin.hjson
fi
