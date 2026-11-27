#!/bin/bash
set -euo pipefail
cd /app/StardewMods
patch -p1 < /solution/gold.patch
echo "oracle: applied upstream fixes 76533d08+ccbf4ab1 (content-patcher/2.0.6)"
