#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 3 ]; then
  echo "Usage: $0 /path/to/server-release.jar /path/to/candidate.jar /path/to/output.jar" >&2
  exit 2
fi

server_jar=$1
candidate_jar=$2
output_jar=$3

project_root=$(cd "$(dirname "$0")" && pwd)
build_root=$(mktemp -d /tmp/mindustry-grader-build.XXXXXX)

trap 'rm -rf "$build_root"' EXIT

mkdir -p "$build_root/classes"

mapfile -t sources < <(find "$project_root/test-runner/src" -name '*.java' -print)
javac --release 17 \
  -cp "$server_jar:$candidate_jar" \
  -d "$build_root/classes" \
  "${sources[@]}"

cp "$project_root/test-runner/plugin.hjson" "$build_root/classes/plugin.hjson"

mkdir -p "$(dirname "$output_jar")"

jar --create \
  --file "$output_jar" \
  -C "$build_root/classes" .

echo "$output_jar"
