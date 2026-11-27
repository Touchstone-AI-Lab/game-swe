#!/usr/bin/env bash
set -euo pipefail

# Replace the starter mod tree with the reference repair, file for file.
mkdir -p /app/mod
find /app/mod -mindepth 1 -delete
cp -a /solution/after/. /app/mod/
echo "oracle: applied the upstream reference repair to /app/mod"
