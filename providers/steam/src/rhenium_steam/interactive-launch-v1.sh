#!/bin/bash
# Explicit preparation only; reuse an existing independent official-client login.
set -euo pipefail
umask 077
[[ $# == 0 && "$HOME" == /home/steamprobe && "$(id -u)" == 1000 && "$DISPLAY" == :0 ]]
client="$HOME/.steam/debian-installation"
[[ -f "$client/config/loginusers.vdf" && -x "$client/steam.sh" ]]
/usr/bin/unshare --user --map-root-user /usr/bin/true
install -d -m 0700 "$XDG_RUNTIME_DIR"
# Independent hard bound also applies if the external controller is interrupted.
exec /usr/bin/timeout --signal=TERM --kill-after=15 1740 \
  dbus-run-session -- "$client/steam.sh" -console -cef-enable-debugging >/dev/null 2>&1
