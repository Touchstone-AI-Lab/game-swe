#!/bin/bash
set -euo pipefail
cd /app/StardewMods
patch -p1 < /solution/gold.patch
echo "oracle: applied upstream fixes 4a12c9af7, 56613e8a1, 601912236, e451ffdcb, f70cd17e4 onto content-patcher/2.6.1"
