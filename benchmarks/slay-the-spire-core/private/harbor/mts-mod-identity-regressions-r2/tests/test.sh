#!/usr/bin/env bash
# Build the submitted ModTheSpire with the licensed game, launch the game with it, and run
# the unchanged r1 private suite inside that game.
set -euo pipefail
export LP_NUM_THREADS=2
# The private suite exactly as r1 staged it; Surefire's default includes select its classes.
SUITE_FILES=(Target.java TargetPatch.java ByRefBoxingTest.java ModIdentityTest.java)
# The two loader-only stand-ins for game classes. On the class path they would shadow the
# licensed game's classes, so the real-game build always leaves them out, whatever their content.
STAND_INS=(com/megacrit/cardcrawl/core/CardCrawlGame.java com/megacrit/cardcrawl/desktop/DesktopLauncher.java)
JUNIT=(org/junit/jupiter/junit-jupiter-api/5.10.2/junit-jupiter-api-5.10.2.jar
       org/junit/jupiter/junit-jupiter-params/5.10.2/junit-jupiter-params-5.10.2.jar
       org/junit/jupiter/junit-jupiter-engine/5.10.2/junit-jupiter-engine-5.10.2.jar
       org/junit/platform/junit-platform-commons/1.10.2/junit-platform-commons-1.10.2.jar
       org/junit/platform/junit-platform-engine/1.10.2/junit-platform-engine-1.10.2.jar
       org/junit/platform/junit-platform-launcher/1.10.2/junit-platform-launcher-1.10.2.jar
       org/opentest4j/opentest4j/1.3.0/opentest4j-1.3.0.jar
       org/apiguardian/apiguardian-api/1.1.2/apiguardian-api-1.1.2.jar)
LOG=/logs/verifier
mkdir -p "$LOG"
chmod 700 "$LOG"
test "$(stat -c '%a' "$LOG")" = 700
chmod -R go-rwx /tests
printf '0\n' > "$LOG/reward.txt"
RUN_NONCE=$(/usr/bin/python3 -I -c 'import secrets; print(secrets.token_hex(24))')
printf '%s\n' "$RUN_NONCE" > "$LOG/nonce.txt"
printf '255\n' > "$LOG/entrypoint-exit.txt"
BUILD_DIR=$(mktemp -d /tmp/mts-verifier.XXXXXXXX)
# Invoked by the EXIT trap installed below.
# shellcheck disable=SC2329
finish() {
    local status=$?
    trap - EXIT
    if [[ ! -f "$LOG/build-exit.txt" ]]; then printf '%s\n' "$status" > "$LOG/build-exit.txt"; fi
    /usr/bin/python3 -I /tests/score.py --observations "$LOG/probe.txt" --nonce-file "$LOG/nonce.txt" --exit-file "$LOG/entrypoint-exit.txt" --output "$LOG"
}
trap finish EXIT
mkdir -p "$BUILD_DIR/project/src/main"
tar -xf /tests/build-template.tar.gz -C "$BUILD_DIR/project"
cp -R /app/modthespire/src/main/java "$BUILD_DIR/project/src/main/"
for stand_in in "${STAND_INS[@]}"; do rm -f "$BUILD_DIR/project/src/main/java/$stand_in"; done
cd "$BUILD_DIR/project"
set +e
mvn -B -o clean test package > "$LOG/build.log" 2>&1
BUILD_EXIT=$?
set -e
printf '%s\n' "$BUILD_EXIT" > "$LOG/build-exit.txt"
if (( BUILD_EXIT != 0 )); then exit "$BUILD_EXIT"; fi
GAME=$BUILD_DIR/game
mkdir -p "$GAME/mods" "$GAME/lib" "$GAME/home" "$GAME/tmp" "$BUILD_DIR/suite-src" "$BUILD_DIR/suite-classes" "$BUILD_DIR/observer-classes"
cp target/ModTheSpire.jar "$GAME/ModTheSpire.jar"
RUNTIME=()
RUNTIME_PATHS=()
for jar in "${JUNIT[@]}"; do
    cp "/root/.m2/repository/$jar" "$GAME/lib/"
    RUNTIME+=("lib/$(basename "$jar")")
    RUNTIME_PATHS+=("$GAME/lib/$(basename "$jar")")
done
CLASSES=()
for file in "${SUITE_FILES[@]}"; do
    cp "/tests/$file" "$BUILD_DIR/suite-src/"
    name=${file%.java}
    if [[ $name == Test* || $name == *Test || $name == *Tests || $name == *TestCase ]]; then CLASSES+=("gcb.$name"); fi
done
JOINED_RUNTIME=$(IFS=:; printf '%s' "${RUNTIME[*]}")
JOINED_PATHS=$(IFS=:; printf '%s' "${RUNTIME_PATHS[*]}")
JOINED_CLASSES=$(IFS=,; printf '%s' "${CLASSES[*]}")
# The suite compiles against the submitted build, as Surefire compiled it against target/classes.
javac -g -encoding UTF-8 -source 8 -target 8 -cp "$GAME/ModTheSpire.jar:$JOINED_PATHS" -d "$BUILD_DIR/suite-classes" "$BUILD_DIR"/suite-src/*.java > "$LOG/probe-build.log" 2>&1
jar cf "$GAME/lib/suite.jar" -C "$BUILD_DIR/suite-classes" .
# The observer mod compiles against the original public SDK, like every other native probe.
javac -g -encoding UTF-8 -source 8 -target 8 -cp "/opt/sts/lib/ModTheSpire.jar:/opt/sts/lib/desktop-1.0.jar:$JOINED_PATHS" -d "$BUILD_DIR/observer-classes" /tests/observer/Observer.java >> "$LOG/probe-build.log" 2>&1
cp /tests/observer/ModTheSpire.json "$BUILD_DIR/observer-classes/"
jar cf "$GAME/mods/suiteobserver.jar" -C "$BUILD_DIR/observer-classes" .
chmod 711 "$BUILD_DIR"
chown -R nobody:nogroup "$GAME"
ln -s /opt/sts/lib/desktop-1.0.jar "$GAME/desktop-1.0.jar"
ln -s /opt/java/openjdk/jre "$GAME/jre"
if ! getent hosts "$(hostname)" >/dev/null; then printf '127.0.0.1 %s\n' "$(hostname)" >> /etc/hosts; fi
cd "$GAME"
set +e
timeout -k 5s 300 runuser -u nobody -- xvfb-run -a -s '-screen 0 1280x720x24' java -Xmx1200m "-Duser.home=$GAME/home" "-Djava.io.tmpdir=$GAME/tmp" "-Dsts.verify.nonce=$RUN_NONCE" "-Dsts.verify.output=$GAME/observations.txt" "-Dsts.verify.classes=$JOINED_CLASSES" -cp "ModTheSpire.jar:lib/suite.jar:$JOINED_RUNTIME" com.evacipated.cardcrawl.modthespire.Loader --imgui --skip-launcher --skip-intro --mods suiteobserver > "$LOG/engine.log" 2>&1
ENGINE_EXIT=$?
set -e
printf '%s\n' "$ENGINE_EXIT" > "$LOG/entrypoint-exit.txt"
if [[ -f "$GAME/observations.txt" && ! -L "$GAME/observations.txt" ]]; then cp "$GAME/observations.txt" "$LOG/probe.txt"; fi
exit 0
