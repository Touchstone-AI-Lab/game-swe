#!/usr/bin/env bash
set -euo pipefail
install -m 0644 /solution/after/vscripts/LinGe/Base.nut /app/linge-hud/vscripts/LinGe/Base.nut
install -m 0644 /solution/after/vscripts/LinGe/MoreSI.nut /app/linge-hud/vscripts/LinGe/MoreSI.nut
cd /app/linge-hud
python3 tools/smoke.py
