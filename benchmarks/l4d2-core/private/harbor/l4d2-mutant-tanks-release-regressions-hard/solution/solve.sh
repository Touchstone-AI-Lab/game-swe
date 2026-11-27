#!/usr/bin/env bash
set -euo pipefail

install -m 0644 \
  /solution/after/addons/sourcemod/scripting/mutant_tanks/mutant_tanks.sp \
  /app/mutant-tanks/addons/sourcemod/scripting/mutant_tanks/mutant_tanks.sp
install -m 0644 \
  /solution/after/addons/sourcemod/scripting/mutant_tanks/abilities2/mt_warp.sp \
  /app/mutant-tanks/addons/sourcemod/scripting/mutant_tanks/abilities2/mt_warp.sp
install -m 0644 \
  /solution/after/addons/sourcemod/scripting/mutant_tanks/abilities/mt_hypno.sp \
  /app/mutant-tanks/addons/sourcemod/scripting/mutant_tanks/abilities/mt_hypno.sp
install -m 0644 \
  /solution/after/addons/sourcemod/scripting/mutant_tanks/mt_abilities.sp \
  /app/mutant-tanks/addons/sourcemod/scripting/mutant_tanks/mt_abilities.sp
install -m 0644 \
  /solution/after/addons/sourcemod/scripting/mutant_tanks/abilities2/mt_panic.sp \
  /app/mutant-tanks/addons/sourcemod/scripting/mutant_tanks/abilities2/mt_panic.sp
patch --no-backup-if-mismatch -p1 -d /app/mutant-tanks < /solution/cooldown.patch

echo "oracle: restored config, health, Warp, Boss, Reward, Hypno, Panic, Rainbow, Acid, and Ammo release behavior"
