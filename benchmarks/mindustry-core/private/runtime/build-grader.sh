#!/usr/bin/env bash
# Package one task's frozen grader suite with the trusted harness as a single
# Mindustry server plugin. Runs while the task's verifier image is built.
#
# Usage: build-grader.sh <suite-dir> <output-jar>
set -euo pipefail

SUITE="$(cd "${1:?usage: build-grader.sh <suite-dir> <output-jar>}" && pwd)"
OUTPUT="${2:?usage: build-grader.sh <suite-dir> <output-jar>}"
MINDUSTRY="${RHENIUM_MINDUSTRY:-/opt/mindustry}"
HOME_DIR="${RHENIUM_HOME:-/opt/rhenium}"
JAR="$MINDUSTRY/server-release.jar"
HARNESS="$HOME_DIR/harness/classes"

[ -d "$HARNESS" ] || { echo "harness classes are missing: $HARNESS" >&2; exit 2; }
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
mapfile -t sources < <(find "$SUITE" -type f -name '*.java' | sort)
[ "${#sources[@]}" -gt 0 ] || { echo "no grader sources under $SUITE" >&2; exit 1; }
mkdir -p "$work/classes"
javac --release 17 -proc:none -Xlint:none -encoding UTF-8 \
  -cp "$JAR:$HARNESS" -d "$work/classes" "${sources[@]}"
[ -f "$work/classes/rhenium/mindustry/grader/TaskSuite.class" ] \
  || { echo "the suite lacks rhenium.mindustry.grader.TaskSuite" >&2; exit 1; }
cp -R "$HARNESS/." "$work/classes/"
install -m 0644 "$HOME_DIR/runtime/plugin.hjson" "$work/classes/plugin.hjson"
mkdir -p "$(dirname "$OUTPUT")"
jar --create --file "$OUTPUT" -C "$work/classes" .
echo "built $OUTPUT"
