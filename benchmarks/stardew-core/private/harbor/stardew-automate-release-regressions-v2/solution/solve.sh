#!/bin/bash
set -euo pipefail
cd /app/StardewMods
patch -p1 < /solution/gold.patch
echo "oracle: restored upstream fixes + location-key pair"
