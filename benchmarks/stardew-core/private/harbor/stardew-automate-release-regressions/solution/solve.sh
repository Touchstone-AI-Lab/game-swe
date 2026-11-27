#!/bin/bash
set -euo pipefail
cd /app/StardewMods
patch -p1 < /solution/gold.patch
echo "oracle: restored the four upstream fixes (0554cd80, e501b71b, f1a3b840, 19b32715) onto automate/2.6.1"
