#!/usr/bin/env bash
set -euo pipefail

cd /app/exodus
patch --dry-run --ignore-whitespace -p1 < /solution/gold.patch
patch --ignore-whitespace -p1 < /solution/gold.patch
echo "oracle: applied the reported Exodus regression fixes"
