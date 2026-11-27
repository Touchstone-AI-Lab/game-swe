#!/bin/bash
set -euo pipefail
cd /app/StardewMods
patch -p1 < /solution/gold.patch
echo "oracle: applied upstream fix e501b71b (automate/2.6.0)"
