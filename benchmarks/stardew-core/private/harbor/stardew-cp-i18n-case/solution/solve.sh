#!/bin/bash
set -euo pipefail
cd /app/StardewMods
patch -p1 < /solution/gold.patch
echo "oracle: applied upstream fix 994f8504 (content-patcher/2.4.4)"
