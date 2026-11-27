#!/bin/bash
# Prepared only; requires approval for the additional foreground-supervised run.
set -euo pipefail
umask 077
[[ $# == 0 && "$HOME" == /home/steamprobe && "$(id -u)" == 1000 ]]
[[ "$DISPLAY" == :0 ]]
client="$HOME/.steam/debian-installation"
[[ -f "$HOME/probe-launch-started" && -f "$HOME/probe-diagnostic-2-started" ]]
[[ ! -e "$HOME/probe-foreground-v3-started" ]]
[[ ! -e "$client/config/loginusers.vdf" && -x "$client/steam.sh" ]]
touch "$HOME/probe-foreground-v3-started"
install -d -m 0700 "$XDG_RUNTIME_DIR"
printf 'stage=official_client_resume_foreground_supervised\n'
exec dbus-run-session -- "$client/steam.sh" -console >/dev/null 2>&1
