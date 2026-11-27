#!/usr/bin/env bash
set -euo pipefail
export LP_NUM_THREADS=2
LOG=/logs/verifier
mkdir -p "$LOG"
chmod 700 "$LOG"
test "$(stat -c '%a' "$LOG")" = 700
chmod -R go-rwx /tests
printf '0\n' > "$LOG/reward.txt"
RUN_NONCE=$(/usr/bin/python3 -I -c 'import secrets; print(secrets.token_hex(24))')
printf '%s\n' "$RUN_NONCE" > "$LOG/nonce.txt"
printf '255\n' > "$LOG/entrypoint-exit.txt"
BUILD_DIR=$(mktemp -d /tmp/downfall-verifier.XXXXXXXX)
finish() {
    local status=$?
    trap - EXIT
    if [[ ! -f "$LOG/build-exit.txt" ]]; then printf '%s\n' "$status" > "$LOG/build-exit.txt"; fi
    /usr/bin/python3 -I /tests/score.py --observations "$LOG/probe.txt" --nonce-file "$LOG/nonce.txt" --exit-file "$LOG/entrypoint-exit.txt" --output "$LOG"
}
trap finish EXIT
mkdir -p "$BUILD_DIR/project/src/main"
tar -xf /tests/build-template.tar.gz -C "$BUILD_DIR/project"
cp -R /app/downfall/src/main/java "$BUILD_DIR/project/src/main/"
cd "$BUILD_DIR/project"
set +e
bash build.sh > "$LOG/build.log" 2>&1
BUILD_EXIT=$?
set -e
printf '%s\n' "$BUILD_EXIT" > "$LOG/build-exit.txt"
if (( BUILD_EXIT != 0 )); then exit "$BUILD_EXIT"; fi
mkdir -p "$BUILD_DIR/game/mods" "$BUILD_DIR/probe-classes"
cp /opt/sts/lib/desktop-1.0.jar /opt/sts/lib/ModTheSpire.jar "$BUILD_DIR/game/"
cp target/Downfall.jar /opt/sts/lib/BaseMod.jar /opt/sts/lib/StSLib.jar "$BUILD_DIR/game/mods/"
ln -s /opt/java/openjdk/jre "$BUILD_DIR/game/jre"
javac -encoding UTF-8 -source 8 -target 8 -cp "$BUILD_DIR/game/mods/Downfall.jar:/opt/sts/lib/*" -d "$BUILD_DIR/probe-classes" /tests/Probe.java > "$LOG/probe-build.log" 2>&1
cp /tests/ModTheSpire.json "$BUILD_DIR/probe-classes/"
jar cf "$BUILD_DIR/game/mods/socketflowscout.jar" -C "$BUILD_DIR/probe-classes" .
ln -s "$BUILD_DIR/game/observations.txt" /logs/probe.txt
mkdir -p "$BUILD_DIR/game/home"
chmod 711 "$BUILD_DIR"
chown -R nobody:nogroup "$BUILD_DIR/game"
if ! getent hosts "$(hostname)" >/dev/null; then printf '127.0.0.1 %s\n' "$(hostname)" >> /etc/hosts; fi
cd "$BUILD_DIR/game"
set +e
timeout -k 5s 450 runuser -u nobody -- xvfb-run -a -s '-screen 0 1280x720x24' java -Xmx2300m "-Duser.home=$BUILD_DIR/game/home" "-Dsts.verify.nonce=$RUN_NONCE" -jar ModTheSpire.jar --imgui --skip-launcher --skip-intro --mods basemod,stslib,downfall,socketflowscout > "$LOG/engine.log" 2>&1
ENGINE_EXIT=$?
set -e
printf '%s\n' "$ENGINE_EXIT" > "$LOG/entrypoint-exit.txt"
if [[ -f "$BUILD_DIR/game/observations.txt" ]]; then cp "$BUILD_DIR/game/observations.txt" "$LOG/probe.txt"; fi
exit 0
