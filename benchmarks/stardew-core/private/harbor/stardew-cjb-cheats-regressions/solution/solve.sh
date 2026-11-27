#!/bin/bash
set -euo pipefail
cd /app/StardewMods
patch -p1 < /solution/gold.patch
echo "oracle: restored upstream fixes 7fcfe1d, ad97de5, 2c05d09, 40e1912, 3a9ba55 (cheats-menu/1.42.0)"
