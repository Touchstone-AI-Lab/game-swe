#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -gt 1 ]; then
  echo "Usage: $0 [/path/to/server-release.jar]" >&2
  exit 2
fi

server_jar=${1:-${MINDUSTRY_SERVER_JAR:-}}

if [ -z "$server_jar" ] || [ ! -f "$server_jar" ]; then
  echo "Mindustry server JAR not found; pass its path or set MINDUSTRY_SERVER_JAR" >&2
  exit 2
fi

project_root=$(cd "$(dirname "$0")" && pwd)
build_root="$project_root/build/candidate"

rm -rf "$build_root"
mkdir -p "$build_root/classes"

mapfile -t sources < <(find "$project_root/src" -name '*.java' -print)
javac --release 17 \
  -cp "$server_jar" \
  -d "$build_root/classes" \
  "${sources[@]}"

cp "$project_root/plugin.hjson" "$build_root/classes/plugin.hjson"

jar --create \
  --file "$build_root/candidate.jar" \
  -C "$build_root/classes" .

echo "$build_root/candidate.jar"
