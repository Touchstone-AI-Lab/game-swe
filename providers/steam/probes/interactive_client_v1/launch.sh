#!/bin/bash
# No capture, keyboard automation, credential arguments or password transport.
set -euo pipefail
umask 077
[[ $# == 0 && "$HOME" == /home/steamprobe && "$(id -u)" == 1000 ]]
[[ "$DISPLAY" == :0 ]]
install -d -m 0700 "$XDG_RUNTIME_DIR"
client="$HOME/.steam/debian-installation"
[[ ! -e "$HOME/probe-launch-started" ]]
touch "$HOME/probe-launch-started"
printf 'stage=bootstrap_download\n'
work="$HOME/bootstrap-work"
mkdir -m 0700 "$work"
curl --fail --silent --show-error --location --connect-timeout 15 --max-time 180 \
  https://repo.steampowered.com/steam/archive/beta/steam_1.0.0.79.tar.gz \
  --output "$work/steam.tar.gz"
printf '%s  %s\n' 3a0012daf5889311c2e1dcf33a587b409019b66d893a52192df6947e18f1ec46 \
  "$work/steam.tar.gz" | sha256sum --check --status
tar -C "$work" -zxf "$work/steam.tar.gz" steam-launcher/bootstraplinux_ubuntu12_32.tar.xz
install -d -m 0700 "$client"
tar -C "$client" -xf "$work/steam-launcher/bootstraplinux_ubuntu12_32.tar.xz"
printf 'stage=bootstrap_verified\n'
# stdout/stderr of the interactive client are not captured by the controller.
# Valve's own private client files remain solely inside the isolated home.
printf 'stage=official_client_start\n'
exec dbus-run-session -- "$client/steam.sh" -console >/dev/null 2>&1
