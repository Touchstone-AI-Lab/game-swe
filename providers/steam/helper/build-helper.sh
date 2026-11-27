#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 RID OUTPUT_DIR" >&2
  exit 2
}

[ "$#" -eq 2 ] || usage
helper_rid=$1
output_dir=$2
helper_root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
scratch=$(mktemp -d "${TMPDIR:-/tmp}/rhenium-steam-helper.XXXXXX")
trap 'find "$scratch" -depth -delete' EXIT

git clone --depth 1 --branch DepotDownloader_3.4.0 \
  https://github.com/SteamRE/DepotDownloader.git "$scratch/depot"
patch --batch --fuzz=0 -d "$scratch/depot" -p1 <"$helper_root/depotdownloader-3.4.0.patch"
install -m 0644 "$helper_root/RheniumProtocol.cs" \
  "$scratch/depot/DepotDownloader/RheniumProtocol.cs"

dotnet publish "$scratch/depot/DepotDownloader/DepotDownloader.csproj" \
  --configuration Release \
  --runtime "$helper_rid" \
  --self-contained true \
  -p:PublishSingleFile=true \
  -p:PublishTrimmed=false \
  -p:AssemblyName=rhenium-steam-helper \
  --output "$output_dir/$helper_rid"

helper_suffix=
case "$helper_rid" in
  win-*) helper_suffix=.exe ;;
esac
mv "$output_dir/$helper_rid/rhenium-steam-helper$helper_suffix" \
  "$output_dir/$helper_rid/rhenium-steam-helper-$helper_rid$helper_suffix"
helper_binary="$output_dir/$helper_rid/rhenium-steam-helper-$helper_rid$helper_suffix"
if [[ $helper_rid == osx-* ]]; then
  command -v codesign >/dev/null 2>&1 || {
    echo "macOS helper releases must be built and ad-hoc signed on macOS" >&2
    exit 1
  }
  codesign --force --sign - "$helper_binary"
  shasum -a 256 "$helper_binary" >"$output_dir/$helper_rid/SHA256SUMS-$helper_rid"
else
  sha256sum "$helper_binary" >"$output_dir/$helper_rid/SHA256SUMS-$helper_rid"
fi
