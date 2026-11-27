#!/bin/bash
set -euo pipefail
cd /app/StardewMods
patch -p1 < /solution/gold.patch
echo "oracle: applied upstream fix f1a3b840 (automate/2.5.0)"
