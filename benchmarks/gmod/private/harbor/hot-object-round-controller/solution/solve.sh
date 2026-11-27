#!/usr/bin/env bash
set -euo pipefail

mkdir -p /app/addon
cp -a /solution/reference/. /app/addon/
echo "oracle: installed the benchmark-authored Garry's Mod reference addon"
