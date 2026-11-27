#!/usr/bin/env bash
set -euo pipefail

root="/workspace/calamity-overhaul"
oracle="$(cd "$(dirname "$0")" && pwd)/after"

cp "$oracle/Content/TimeFreezes/NetworkEntityIdentity.cs" "$root/Content/TimeFreezes/NetworkEntityIdentity.cs"
cp "$oracle/Content/TimeFreezes/TimeControlReplicationSystem.cs" "$root/Content/TimeFreezes/TimeControlReplicationSystem.cs"
