#!/usr/bin/env bash
set -euo pipefail

if [[ $# != 3 || ! $1 = /* || ! $2 = /* || ! $3 =~ ^[0-9]+$ ]]; then
  echo 'usage: install-server.sh <absolute-steamcmd> <absolute-install-dir> <expected-build>' >&2
  exit 2
fi
steamcmd=$1
install_dir=$2
expected_build=$3

# A fresh SteamCMD self-update can leave app metadata unavailable on its first
# install request. Retry the same anonymous request; never relax the build pin.
installed=false
for attempt in 1 2 3; do
  if "$steamcmd" \
    +@ShutdownOnFailedCommand 1 +@NoPromptForPassword 1 \
    +force_install_dir "$install_dir" \
    +login anonymous +app_update 343050 validate +quit; then
    installed=true
    break
  fi
  if [[ $attempt != 3 ]]; then sleep 5; fi
done
if [[ $installed != true ]]; then
  echo 'anonymous DST dedicated-server installation failed after three attempts' >&2
  exit 1
fi

grep -Eq "\"buildid\"[[:space:]]+\"${expected_build}\"" \
  "$install_dir/steamapps/appmanifest_343050.acf"
test -x "$install_dir/bin64/dontstarve_dedicated_server_nullrenderer_x64"
test -d "$install_dir/mods"
