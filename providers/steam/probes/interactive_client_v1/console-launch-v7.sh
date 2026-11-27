#!/bin/bash
# Reuse the operator's isolated client state. No login input or screen capture.
set -euo pipefail
umask 077
[[ $# == 0 && "$HOME" == /home/steamprobe && "$(id -u)" == 1000 ]]
[[ "$DISPLAY" == :0 ]]
client="$HOME/.steam/debian-installation"
[[ -f "$HOME/probe-shm-v5-started" && ! -e "$HOME/probe-console-v7-started" ]]
[[ -f "$client/config/loginusers.vdf" && -x "$client/steam.sh" ]]
touch "$HOME/probe-console-v7-started"
/usr/bin/unshare --user --map-root-user /usr/bin/true
install -d -m 0700 "$XDG_RUNTIME_DIR"
exec dbus-run-session -- "$client/steam.sh" -console -cef-enable-debugging >/dev/null 2>&1
