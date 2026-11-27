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
cd "$BUILD_DIR/project"
set +e
mvn -B -o clean test package > "$LOG/build.log" 2>&1
BUILD_EXIT=$?
set -e
printf '%s\n' "$BUILD_EXIT" > "$LOG/build-exit.txt"
if (( BUILD_EXIT != 0 )); then exit "$BUILD_EXIT"; fi
chmod 711 "$BUILD_DIR"
if ! getent hosts "$(hostname)" >/dev/null; then printf '127.0.0.1 %s\n' "$(hostname)" >> /etc/hosts; fi
set +e
/usr/bin/python3 -I /tests/run_probe.py --jar "$BUILD_DIR/project/target/ModTheSpire.jar" --runtime "$BUILD_DIR/runtime" --nonce-file "$LOG/nonce.txt" --output "$LOG/probe.txt" --engine-log "$LOG/engine.log" > "$LOG/observer.log" 2>&1
OBSERVER_EXIT=$?
set -e
printf '%s\n' "$OBSERVER_EXIT" > "$LOG/entrypoint-exit.txt"
exit 0
