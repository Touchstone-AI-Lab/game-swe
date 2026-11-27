#!/usr/bin/env bash
set -euo pipefail
mkdir -p /workspace/mindustry/src
cp /solution/ReservationLedger.java /workspace/mindustry/src/ReservationLedger.java
cp /solution/ItemReservationLedgerPlugin.java /workspace/mindustry/src/ItemReservationLedgerPlugin.java
cp /solution/plugin.hjson /workspace/mindustry/plugin.hjson
cp /solution/build-reference.sh /workspace/mindustry/build-reference.sh
