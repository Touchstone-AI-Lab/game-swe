#!/usr/bin/env bash
set -euo pipefail

root="/workspace/aequus"
oracle="$(cd "$(dirname "$0")" && pwd)/after"

cp "$oracle/Common/Carpentry/BuildChallengeSaveData.cs" "$root/Common/Carpentry/BuildChallengeSaveData.cs"
cp "$oracle/Common/Carpentry/BuildBuffsData.cs" "$root/Common/Carpentry/BuildBuffsData.cs"
cp "$oracle/Common/Carpentry/CarpentrySystem.cs" "$root/Common/Carpentry/CarpentrySystem.cs"
cp "$oracle/Common/Carpentry/CarpentryPlayer.cs" "$root/Common/Carpentry/CarpentryPlayer.cs"
