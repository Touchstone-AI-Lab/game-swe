#!/usr/bin/env bash
set -euo pipefail
readonly MODS=/opt/rimworld/Mods
readonly SAVEDATA=/state/rimworld
readonly OUT=/logs/verifier
readonly ASSEMBLIES=/assemblies
umask 077
ulimit -f 65536
: "${RHENIUM_EVALUATION_ID:?missing evaluation ID}"
: "${RHENIUM_EVALUATION_NONCE:?missing evaluation nonce}"
: "${RHENIUM_TASK_KEY:?missing canonical task key}"
: "${RHENIUM_SUBMISSION_SHA256:?missing submission hash}"
: "${RHENIUM_CANDIDATE_ASSEMBLY_SHA256:?missing candidate assembly hash}"
mkdir -p "$OUT" "$SAVEDATA/Config" "$MODS/Candidate/About" "$MODS/Candidate/1.6/Assemblies"   "$MODS/RheniumVerifier/About" "$MODS/RheniumVerifier/1.6/Assemblies"
cp -a /opt/rhenium/runtime-mods/Harmony "$MODS/Harmony"
cp "$ASSEMBLIES/ProjectRimFactory.dll" "$MODS/Candidate/1.6/Assemblies/ProjectRimFactory.dll"
cp "/opt/rhenium/ModMetadata/ProjectRimFactory/About.xml" "$MODS/Candidate/About/About.xml"
cp /opt/rhenium/ModMetadata/Verifier/About.xml "$MODS/RheniumVerifier/About/About.xml"
cp "$ASSEMBLIES/RheniumRimWorldVerifier.dll" "$MODS/RheniumVerifier/1.6/Assemblies/RheniumRimWorldVerifier.dll"
cp /opt/rhenium/ModsConfig.xml "$SAVEDATA/Config/ModsConfig.xml"
set +e
timeout --signal=TERM --kill-after=20s 600s xvfb-run -a -s '-screen 0 1280x720x24 +extension GLX'   /opt/rimworld/RimWorldLinux -savedatafolder="$SAVEDATA" -screen-fullscreen 0   -screen-width 1280 -screen-height 720 -logFile "$OUT/Player.log"
status=$?
set -e
if [[ $status -ne 0 ]]; then echo "RimWorld exited with status $status" >&2; exit "$status"; fi
test -s "$OUT/observations.json"
