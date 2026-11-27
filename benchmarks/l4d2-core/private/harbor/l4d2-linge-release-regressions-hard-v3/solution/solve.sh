#!/usr/bin/env bash
set -euo pipefail

install -m 0644 \
  /solution/after/vscripts/LinGe/HUD.nut \
  /app/linge-hud/vscripts/LinGe/HUD.nut
cd /app/linge-hud
python3 /solution/solve.py
echo "oracle: applied the reference release-regression repairs"
