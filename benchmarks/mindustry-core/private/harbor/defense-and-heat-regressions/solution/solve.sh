#!/usr/bin/env bash
set -euo pipefail

mkdir -p /app/mindustry
cp -a /solution/after/. /app/mindustry/
echo "oracle: applied the reference repair to the Mindustry source tree"
