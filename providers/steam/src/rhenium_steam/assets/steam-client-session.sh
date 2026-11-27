#!/usr/bin/env bash
# Run the official Steam client headlessly inside the bootstrap container.
#
# The client is installed into the mounted client home from the pinned bootstrap archive and
# started on a virtual display. Every login QR code the client renders is decoded and written
# to /shots/qr.txt so the provider can show it in the terminal or the Web UI. The client
# self-updates from Valve, so its exact version is not pinned and must not be claimed as such.
set -uo pipefail

export HOME=${HOME:-/home/azureuser}
export DISPLAY=:99
export LIBGL_ALWAYS_SOFTWARE=1
export GDK_BACKEND=x11
export SDL_VIDEODRIVER=x11
export GTK_A11Y=none
export XDG_RUNTIME_DIR=/tmp/xdg-rhenium

STEAM_DIR="$HOME/.steam/debian-installation"
BOOTSTRAP_VERSION=1.0.0.79
BOOTSTRAP_SHA256=3a0012daf5889311c2e1dcf33a587b409019b66d893a52192df6947e18f1ec46
BOOTSTRAP_URL="https://repo.steampowered.com/steam/archive/beta/steam_${BOOTSTRAP_VERSION}.tar.gz"

fail() {
  printf 'steam-client-session: %s\n' "$1" >&2
  exit 1
}

install_client() {
  [ -x "$STEAM_DIR/steam.sh" ] && return 0
  local work
  work=$(mktemp -d) || fail "could not create a temporary directory"
  # Same pinned archive and verification the Debian steam-installer launcher uses, without its
  # interactive confirmation dialog.
  curl -fsSL -o "$work/steam.tar.gz" "$BOOTSTRAP_URL" || fail "could not download the Steam bootstrap"
  printf '%s  %s\n' "$BOOTSTRAP_SHA256" "$work/steam.tar.gz" | sha256sum -c - >/dev/null 2>&1 ||
    fail "Steam bootstrap SHA-256 mismatch"
  tar -C "$work" -zxf "$work/steam.tar.gz" steam-launcher/bootstraplinux_ubuntu12_32.tar.xz ||
    fail "could not unpack the Steam bootstrap"
  install -d -m 0755 "$STEAM_DIR"
  tar -C "$STEAM_DIR" -xf "$work/steam-launcher/bootstraplinux_ubuntu12_32.tar.xz" ||
    fail "could not install the Steam client"
  rm -rf "$work"
}

install -d -m 0700 "$XDG_RUNTIME_DIR"
install -d -m 0755 /shots
install_client

Xvfb :99 -screen 0 1280x800x24 -nolisten tcp >>/shots/xvfb.log 2>&1 &
for _ in $(seq 1 30); do
  xdotool getmouselocation >/dev/null 2>&1 && break
  sleep 1
done
openbox >>/shots/openbox.log 2>&1 &

# The Chromium sandbox inside the client stays enabled; only GPU acceleration is disabled
# because the virtual display has no GPU.
dbus-run-session -- "$STEAM_DIR/steam.sh" "$@" >>/shots/steam.log 2>&1 &

# A decode can fail on a screenshot taken mid-refresh, so only report the QR code as gone
# after several consecutive misses. An empty qr.txt tells the provider it was scanned.
misses=0
rounds=0
while true; do
  # The client restarts itself after self-updating; make sure its window is mapped so the
  # sign-in QR code is on screen where the screenshot can reach it.
  rounds=$((rounds + 1))
  if [ $((rounds % 5)) -eq 1 ]; then
    for window in $(xdotool search --name '^Steam$' 2>/dev/null); do
      xdotool windowmap "$window" >/dev/null 2>&1 || true
    done
  fi
  if import -window root /shots/latest.next.png 2>/dev/null; then
    mv -f /shots/latest.next.png /shots/latest.png
  fi
  if zbarimg -q --raw /shots/latest.png >/shots/qr.next 2>/dev/null; then
    misses=0
    mv -f /shots/qr.next /shots/qr.txt
  else
    rm -f /shots/qr.next
    misses=$((misses + 1))
    if [ "$misses" -ge 3 ] && [ -s /shots/qr.txt ]; then
      : >/shots/qr.txt
    fi
  fi
  sleep 2
done
