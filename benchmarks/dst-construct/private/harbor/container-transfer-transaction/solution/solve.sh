#!/usr/bin/env bash
set -euo pipefail

mkdir -p /app/mod
cp -a /solution/reference/. /app/mod/
echo "oracle: installed the benchmark-authored Don't Starve Together reference mod"
