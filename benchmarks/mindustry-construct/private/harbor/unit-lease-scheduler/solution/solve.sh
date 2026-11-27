#!/usr/bin/env bash
set -euo pipefail

mkdir -p /workspace/mindustry/src

cp /solution/LeaseScheduler.java \
   /workspace/mindustry/src/LeaseScheduler.java

cp /solution/UnitLeaseSchedulerPlugin.java \
   /workspace/mindustry/src/UnitLeaseSchedulerPlugin.java

if [ -f /solution/plugin.hjson ]; then
    cp /solution/plugin.hjson /workspace/mindustry/plugin.hjson
fi
