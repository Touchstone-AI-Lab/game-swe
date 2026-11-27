#!/usr/bin/env bash
set -euo pipefail

install -m 0644 \
  /solution/after/sourcemod/scripting/l4dd/l4dd_natives.sp \
  /app/left4dhooks/sourcemod/scripting/l4dd/l4dd_natives.sp
install -m 0644 \
  /solution/after/sourcemod/scripting/l4dd/l4dd_forwards.sp \
  /app/left4dhooks/sourcemod/scripting/l4dd/l4dd_forwards.sp
install -m 0644 \
  /solution/after/sourcemod/scripting/include/left4dhooks.inc \
  /app/left4dhooks/sourcemod/scripting/include/left4dhooks.inc
patch --batch --forward --no-backup-if-mismatch -d /app/left4dhooks -p1 < /solution/animhook.patch
patch --batch --forward --no-backup-if-mismatch -d /app/left4dhooks -p1 < /solution/campaignscores.patch
patch --batch --forward --no-backup-if-mismatch -d /app/left4dhooks -p1 < /solution/meleeinfo.patch

echo "oracle: applied the twelve frozen Left4DHooks repairs"
