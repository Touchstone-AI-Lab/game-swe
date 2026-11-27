#!/bin/bash
set -uo pipefail

LOG_ROOT="${LOGS_DIR:-/logs}/verifier"
mkdir -p "$LOG_ROOT"

python3 /tests/verify.py \
  --submission /app/mod \
  --spec /tests/spec.json \
  --behavior /tests/behavior.lua \
  --server /tests/server.lua \
  --logs "$LOG_ROOT"
