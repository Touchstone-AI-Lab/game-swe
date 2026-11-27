#!/usr/bin/env bash
set -euo pipefail

export HOME=/state/home
export GCB_TERRARIA_REPORT="${GCB_TERRARIA_REPORT:-/reports/engine-report.json}"

install -d -m 0755 "$HOME" /workspace/engine /workspace/solution \
  /state/tModLoader/Mods
test -d "$(dirname "$GCB_TERRARIA_REPORT")"
cp -R /engine/. /workspace/engine/

if [[ -d /solution ]]; then
  cp -R /solution/. /workspace/solution/
fi

mapfile -t projects < <(find /workspace/engine -mindepth 2 -maxdepth 2 -name '*.csproj' -type f | sort)
if [[ ${#projects[@]} -ne 1 ]]; then
  echo "expected exactly one Terraria engine verifier project" >&2
  exit 81
fi

dotnet build "${projects[0]}" \
  --configuration Release \
  -p:RestoreIgnoreFailedSources=true \
  -p:RestoreSources=/opt/nuget-source \
  -p:tMLSteamPath=/opt/tmodloader/ \
  -p:CandidateRoot=/workspace/solution \
  '-p:ExtraBuildModFlags=-savedirectory /state' \
  -v:minimal

cd /opt/tmodloader
set +e
dotnet /opt/tmodloader/tModLoader.dll \
  -server \
  -nosteam \
  -savedirectory /state \
  -world /state/GcbBenchmark.wld \
  -worldname GcbBenchmark \
  -autocreate 1 \
  -maxplayers 1
status=$?
set -e

if [[ -f "$GCB_TERRARIA_REPORT" && ! -L "$GCB_TERRARIA_REPORT" ]]; then
  report_size=$(stat --format='%s' "$GCB_TERRARIA_REPORT")
  if (( report_size <= 262144 )); then
    printf '\nGCB_TERRARIA_REPORT_V1='
    base64 --wrap=0 "$GCB_TERRARIA_REPORT"
    printf '\n'
  fi
fi

exit "$status"
