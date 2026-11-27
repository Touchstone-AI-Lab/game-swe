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
for target_platform in windows linux; do
  installed=false
  for attempt in 1 2 3; do
    if "$steamcmd" \
      +@sSteamCmdForcePlatformType "$target_platform" \
      +force_install_dir "$install_dir" \
      +login anonymous +app_update 222860 validate +quit; then
      installed=true
      break
    fi
    if [[ $attempt != 3 ]]; then sleep 5; fi
  done
  if [[ $installed != true ]]; then
    echo "anonymous L4D2 $target_platform installation failed after three attempts" >&2
    exit 1
  fi
done

grep -Eq "\"buildid\"[[:space:]]+\"${expected_build}\"" \
  "$install_dir/steamapps/appmanifest_222860.acf"
test -x "$install_dir/srcds_run"
