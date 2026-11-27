#!/bin/bash
set -euo pipefail
cd /app/StardewMods
patch -p1 < /solution/gold.patch
echo "oracle: restored the upstream incubator guards (d336d22a)"
