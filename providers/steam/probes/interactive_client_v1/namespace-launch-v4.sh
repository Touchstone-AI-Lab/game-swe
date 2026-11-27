#!/bin/bash
# One explicitly approved namespace-permission experiment; no credential capture.
set -euo pipefail
umask 077
[[ $# == 0 && "$HOME" == /home/steamprobe && "$(id -u)" == 1000 ]]
[[ "$DISPLAY" == :0 ]]
client="$HOME/.steam/debian-installation"
[[ -f "$HOME/probe-foreground-v3-started" && ! -e "$HOME/probe-namespace-v4-started" ]]
[[ ! -e "$client/config/loginusers.vdf" && -x "$client/steam.sh" ]]
touch "$HOME/probe-namespace-v4-started"
/usr/bin/unshare --user --map-root-user /usr/bin/true
printf 'stage=user_namespace_preflight_passed\n'
install -d -m 0700 "$XDG_RUNTIME_DIR"
exec dbus-run-session -- "$client/steam.sh" -console >/dev/null 2>&1
