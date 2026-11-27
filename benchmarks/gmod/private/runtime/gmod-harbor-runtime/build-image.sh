#!/usr/bin/env bash
# Build the local Garry's Mod Addons verifier image from an operator-retained,
# pinned Linux Dedicated Server installation. This script never logs in to Steam
# and never downloads, updates or repairs the server: it only checks the pin and
# hands the directory to Docker as a named build context.
#
# Usage: build-image.sh <absolute-server-root>
set -euo pipefail

BUILD_ID=23150012
TAG="gcb-gmod-addons-verifier:${BUILD_ID}"

if [[ $# != 1 || ! $1 = /* ]]; then
  echo 'usage: build-image.sh <absolute-server-root>' >&2
  exit 2
fi
server_root=$1
context="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
manifest="$server_root/steamapps/appmanifest_4020.acf"

if [[ ! -f $manifest ]] || ! grep -Eq "\"buildid\"[[:space:]]+\"${BUILD_ID}\"" "$manifest"; then
  echo "server root is not the pinned App 4020 build ${BUILD_ID}; refusing to build" >&2
  exit 1
fi
if [[ ! -x $server_root/srcds_linux ]]; then
  echo 'server root has no executable srcds_linux (a Linux installation is required)' >&2
  exit 1
fi

exec docker build \
  --platform=linux/amd64 \
  --build-arg "GMOD_BUILD_ID=${BUILD_ID}" \
  --build-context "server=${server_root}" \
  --tag "$TAG" \
  "$context"
