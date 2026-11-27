#!/usr/bin/env bash
# One-time preparation of the Paper server inside the verifier base image.
#
# Runs while the image is built (network available): patches the Mojang server
# with paperclip, records the server classpath, compiles the trusted GcbHarness
# plugin, installs the benchmark server configuration, boots the server once so
# the fixed-seed flat world exists, and asserts every product is in place.
# Evaluation containers never repeat any of this.
set -euo pipefail

PAPER="${GCB_PAPER:-/opt/paper}"
HOME_DIR="${GCB_HOME:-/opt/gcb}"
RUNTIME="$HOME_DIR/runtime"
JAR="$PAPER/paper-1.21.11-132.jar"
VERSION_JAR="$PAPER/versions/1.21.11/paper-1.21.11.jar"

[ -f "$JAR" ] || { echo "server jar is missing: $JAR" >&2; exit 1; }
grep -Eqi '^[[:space:]]*eula[[:space:]]*=[[:space:]]*true[[:space:]]*$' "$PAPER/eula.txt" \
  || { echo "eula.txt does not accept the EULA" >&2; exit 1; }

cd "$PAPER"

echo "== paperclip patch-only bootstrap"
java -Dpaperclip.patchonly=true -jar "$JAR"
[ -f "$VERSION_JAR" ] || { echo "paperclip did not produce $VERSION_JAR" >&2; exit 1; }
[ -d "$PAPER/libraries" ] || { echo "paperclip did not produce libraries/" >&2; exit 1; }

echo "== recording the server classpath"
{
  echo "$VERSION_JAR"
  find "$PAPER/libraries" -type f -name '*.jar' | sort
} > "$HOME_DIR/classpath.txt"
paper_api="$(find "$PAPER/libraries/io/papermc/paper/paper-api" -name 'paper-api-*.jar' | head -n 1 || true)"
[ -n "$paper_api" ] || { echo "paper-api jar is missing from libraries/" >&2; exit 1; }
paste -sd: "$HOME_DIR/classpath.txt" > "$HOME_DIR/classpath.colon"

echo "== compiling GcbHarness"
bash "$HOME_DIR/harness/src/build.sh" "$HOME_DIR/classpath.colon" "$HOME_DIR/harness/gcb-harness.jar"
[ -s "$HOME_DIR/harness/gcb-harness.jar" ] || { echo "harness jar was not produced" >&2; exit 1; }

echo "== installing server configuration"
install -m 0644 "$RUNTIME/server.properties" "$PAPER/server.properties"
install -d "$PAPER/config" "$PAPER/plugins/bStats"
install -m 0644 "$RUNTIME/paper-global.yml" "$PAPER/config/paper-global.yml"
install -m 0644 "$RUNTIME/bstats-config.yml" "$PAPER/plugins/bStats/config.yml"
install -m 0755 "$RUNTIME/javac-build.sh" "$HOME_DIR/javac-build.sh"

echo "== generating the benchmark world"
cp "$HOME_DIR/harness/gcb-harness.jar" "$PAPER/plugins/gcb-harness.jar"
timeout 600 java -Xms1G -Xmx2G -XX:+UseG1GC \
  -Dgcb.mode=bootstrap \
  -Dterminal.jline=false -Dterminal.ansi=false -Dnet.kyori.ansi.colorLevel=none \
  -jar "$JAR" --nogui > "$HOME_DIR/bootstrap-boot.log" 2>&1 \
  || { echo "bootstrap boot failed" >&2; tail -n 60 "$HOME_DIR/bootstrap-boot.log" >&2; exit 1; }
grep -q 'GCB bootstrap: world ready' "$HOME_DIR/bootstrap-boot.log" \
  || { echo "the harness never reported the world as ready" >&2; tail -n 60 "$HOME_DIR/bootstrap-boot.log" >&2; exit 1; }
rm -f "$PAPER/plugins/gcb-harness.jar"
rm -rf "$PAPER/plugins/spark" "$PAPER/logs"

echo "== asserting the prepared layout"
for required in "$PAPER/world/level.dat" "$PAPER/server.properties" "$PAPER/config/paper-global.yml" \
    "$HOME_DIR/classpath.txt" "$HOME_DIR/harness/gcb-harness.jar" "$HOME_DIR/javac-build.sh"; do
  [ -e "$required" ] || { echo "missing after bootstrap: $required" >&2; exit 1; }
done
[ -z "$(find "$PAPER/plugins" -maxdepth 1 -name '*.jar' -print -quit)" ] \
  || { echo "plugins/ must hold no jar after bootstrap" >&2; exit 1; }
echo "== bootstrap complete"
