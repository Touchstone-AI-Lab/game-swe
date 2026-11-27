#!/bin/bash
set -euo pipefail
cd /app/StardewMods
patch -p1 < /solution/gold.patch
echo "oracle: restored 19b32715 + f1a3b840 + 001e64aa and the location-key pair"
