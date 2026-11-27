#!/usr/bin/env bash
# Trusted dependency-free build of a Paper plugin: compile src/main/java against
# the recorded server classpath and package it with src/main/resources.
# Used for clean-room synthetic tasks; repository tasks use their own build tool.
#
# Usage: javac-build.sh <plugin-dir> <output-jar>
set -euo pipefail

PLUGIN="$(cd "${1:?usage: javac-build.sh <plugin-dir> <output-jar>}" && pwd)"
OUTPUT="${2:?usage: javac-build.sh <plugin-dir> <output-jar>}"
HOME_DIR="${GCB_HOME:-/opt/gcb}"
CLASSPATH_FILE="$HOME_DIR/classpath.colon"

[ -f "$CLASSPATH_FILE" ] || { echo "server classpath is missing: $CLASSPATH_FILE" >&2; exit 2; }
[ -d "$PLUGIN/src/main/java" ] || { echo "src/main/java is missing" >&2; exit 1; }
[ -f "$PLUGIN/src/main/resources/plugin.yml" ] || { echo "src/main/resources/plugin.yml is missing" >&2; exit 1; }

classes="$(mktemp -d)"
trap 'rm -rf "$classes"' EXIT
mapfile -t sources < <(find "$PLUGIN/src/main/java" -type f -name '*.java' | sort)
[ "${#sources[@]}" -gt 0 ] || { echo "no Java sources under src/main/java" >&2; exit 1; }

javac --release 21 -proc:none -Xlint:none -encoding UTF-8 \
  -cp "$(cat "$CLASSPATH_FILE")" -d "$classes" "${sources[@]}"
cp -R "$PLUGIN/src/main/resources/." "$classes/"
mkdir -p "$(dirname "$OUTPUT")"
jar --create --file "$OUTPUT" -C "$classes" .
echo "built $OUTPUT"
