#!/usr/bin/env bash
set -euo pipefail
LOG=/logs/verifier
mkdir -p "$LOG"
chmod 700 "$LOG"
chmod -R go-rwx /tests
printf '0\n' > "$LOG/reward.txt"
RUN_NONCE=$(/usr/bin/python3 -I -c 'import secrets; print(secrets.token_hex(24))')
printf '%s\n' "$RUN_NONCE" > "$LOG/nonce.txt"
printf '255\n' > "$LOG/entrypoint-exit.txt"
BUILD_DIR=$(mktemp -d /tmp/mts-verifier.XXXXXXXX)
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
cd "$BUILD_DIR/project"
set +e
mvn -B -o clean test package > "$LOG/build.log" 2>&1
BUILD_EXIT=$?
set -e
printf '%s\n' "$BUILD_EXIT" > "$LOG/build-exit.txt"
if (( BUILD_EXIT != 0 )); then exit "$BUILD_EXIT"; fi
chmod 711 "$BUILD_DIR"
set +e
/usr/bin/python3 -I /tests/run_probe.py --jar "$BUILD_DIR/project/target/ModTheSpire.jar" --runtime "$BUILD_DIR/runtime" --nonce-file "$LOG/nonce.txt" --output "$LOG/probe.txt" > "$LOG/observer.log" 2>&1
OBSERVER_EXIT=$?
set -e
printf '%s\n' "$OBSERVER_EXIT" > "$LOG/entrypoint-exit.txt"
exit 0
