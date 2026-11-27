#!/usr/bin/env bash
set -euo pipefail

for file in \
  l4d2_incap_fire_fix.sp \
  l4d2_weapon_attributes.sp \
  l4d2_fix_changelevel.sp
do
  install -m 0644 \
    "/solution/after/addons/sourcemod/scripting/${file}" \
    "/app/l4d2-competitive/addons/sourcemod/scripting/${file}"
done

echo "oracle: applied the three frozen Competitive Rework repairs"
