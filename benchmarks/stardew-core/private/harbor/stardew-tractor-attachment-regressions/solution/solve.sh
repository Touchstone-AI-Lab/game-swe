#!/bin/bash
set -euo pipefail
cd /app/StardewMods
patch -p1 < /solution/gold.patch
echo "oracle: restored upstream fixes a92f4f9cd, f35bc8604, 6ad0cb951, bd38fead3 (tractor-mod/4.24.4)"
