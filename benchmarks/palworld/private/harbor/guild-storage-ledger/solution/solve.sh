#!/bin/bash
set -euo pipefail

mkdir -p /app/mod
cp -a /solution/reference/. /app/mod/
echo "oracle: installed the benchmark-authored Palworld UE4SS reference mod"
