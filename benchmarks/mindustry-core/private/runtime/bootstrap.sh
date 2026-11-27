#!/usr/bin/env bash
# One-time preparation inside the verifier base image (network available).
#
# Compiles the trusted Rhenium harness against the pinned server jar, then boots the
# real dedicated server once with the harness in bootstrap mode to prove that the jar,
# the JVM and the plugin loader work together. Evaluation containers never repeat this.
set -euo pipefail

MINDUSTRY="${RHENIUM_MINDUSTRY:-/opt/mindustry}"
HOME_DIR="${RHENIUM_HOME:-/opt/rhenium}"
JAR="$MINDUSTRY/server-release.jar"
HARNESS="$HOME_DIR/harness"

[ -f "$JAR" ] || { echo "server jar is missing: $JAR" >&2; exit 1; }

echo "== compiling the Rhenium harness"
rm -rf "$HARNESS/classes"
mkdir -p "$HARNESS/classes"
mapfile -t sources < <(find "$HARNESS/src" -type f -name '*.java' | sort)
[ "${#sources[@]}" -gt 0 ] || { echo "no harness sources" >&2; exit 1; }
javac --release 17 -proc:none -Xlint:none -encoding UTF-8 \
  -cp "$JAR" -d "$HARNESS/classes" "${sources[@]}"
install -m 0755 "$HOME_DIR/runtime/build-grader.sh" "$HOME_DIR/build-grader.sh"

echo "== booting the pinned server with the harness in bootstrap mode"
boot="$(mktemp -d)"
trap 'rm -rf "$boot"' EXIT
mkdir -p "$boot/plugin" "$boot/server/config/mods"
cp -R "$HARNESS/classes/." "$boot/plugin/"
install -m 0644 "$HOME_DIR/runtime/plugin.hjson" "$boot/plugin/plugin.hjson"
jar --create --file "$boot/server/config/mods/rhenium-harness.jar" -C "$boot/plugin" .
(
  cd "$boot/server"
  timeout 300 java -Xmx1g -Djava.awt.headless=true -Drhenium.harness.mode=bootstrap \
    -cp "$JAR" mindustry.server.ServerLauncher < /dev/null > "$boot/boot.log" 2>&1
) || { echo "bootstrap boot failed" >&2; tail -n 60 "$boot/boot.log" >&2; exit 1; }
grep -q 'RHENIUM_HARNESS_READY' "$boot/boot.log" \
  || { echo "the harness never reported ready" >&2; tail -n 60 "$boot/boot.log" >&2; exit 1; }
grep 'RHENIUM_HARNESS_READY' "$boot/boot.log"
echo "== bootstrap complete"
