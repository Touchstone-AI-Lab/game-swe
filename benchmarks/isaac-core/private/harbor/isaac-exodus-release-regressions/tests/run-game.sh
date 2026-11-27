#!/usr/bin/env bash
set -uo pipefail

export HOME=/home/azureuser
export DISPLAY=:99
export LIBGL_ALWAYS_SOFTWARE=1
export GDK_BACKEND=x11
export SDL_VIDEODRIVER=x11
export XDG_RUNTIME_DIR=/tmp/steam-runtime-azureuser
export GTK_A11Y=none

steam="$HOME/.steam/debian-installation/steam.sh"
runtime_log=/logs/verifier/runtime.log
game_log="$HOME/.local/share/binding of isaac afterbirth+/log.txt"
xvfb_pid=""
openbox_pid=""

# Invoked indirectly by the EXIT trap below.
# shellcheck disable=SC2317,SC2329
shutdown_runtime() {
  "$steam" -shutdown >>"$runtime_log" 2>&1 || true
  for _ in $(seq 1 20); do
    pgrep -x steam >/dev/null 2>&1 || break
    sleep 1
  done
  [ -z "$openbox_pid" ] || kill "$openbox_pid" >/dev/null 2>&1 || true
  [ -z "$xvfb_pid" ] || kill "$xvfb_pid" >/dev/null 2>&1 || true
}
trap shutdown_runtime EXIT

install -d -m 0700 "$XDG_RUNTIME_DIR"
Xvfb :99 -screen 0 1280x800x24 -nolisten tcp >>"$runtime_log" 2>&1 &
xvfb_pid=$!
for _ in $(seq 1 20); do
  xdotool getmouselocation >/dev/null 2>&1 && break
  sleep 1
done
openbox >>"$runtime_log" 2>&1 &
openbox_pid=$!

dbus-run-session -- "$steam" \
  -silent -offline -cef-disable-gpu -cef-force-opaque-backgrounds -no-cef-sandbox \
  >>"$runtime_log" 2>&1 &

steam_started=0
for _ in $(seq 1 90); do
  if pgrep -x steam >/dev/null 2>&1; then
    steam_started=1
    break
  fi
  sleep 1
done
if [ "$steam_started" -ne 1 ]; then
  echo "GCB_RUNTIME_INVALID steam_start_timeout" | tee -a "$runtime_log"
  exit 10
fi

"$steam" -applaunch 250900 >>"$runtime_log" 2>&1 || true

game_started=0
for _ in $(seq 1 180); do
  if pgrep -x isaac.x64 >/dev/null 2>&1; then
    game_started=1
    echo "GCB_ISAAC_STARTED" | tee -a "$runtime_log"
    break
  fi
  sleep 1
done
if [ "$game_started" -ne 1 ]; then
  echo "GCB_RUNTIME_INVALID game_start_timeout" | tee -a "$runtime_log"
  exit 11
fi

send_game_key() {
  local key=$1
  local window
  window=$(xdotool search --onlyvisible --name 'Binding of Isaac' 2>/dev/null | tail -n 1)
  [ -n "$window" ] || return 1
  xdotool windowactivate "$window" >/dev/null 2>&1 || true
  xdotool key --clearmodifiers "$key" >/dev/null 2>&1
}

# Skip the opening cutscene, then advance through Press Start, New Run, and
# the default character selection. Re-resolve the window because SDL replaces
# it while transitioning out of the intro.
sleep 5
send_game_key Escape || true
suite_started=0
for _ in $(seq 1 20); do
  if grep -q '\[GCB_RUNTIME\] suite_started' "$game_log" 2>/dev/null; then
    suite_started=1
    break
  fi
  pgrep -x isaac.x64 >/dev/null 2>&1 || break
  sleep 2
  send_game_key Return || true
done
if [ "$suite_started" -ne 1 ]; then
  echo "GCB_RUNTIME_INVALID suite_start_timeout" | tee -a "$runtime_log"
  exit 12
fi

for _ in $(seq 1 180); do
  if grep -q '\[GCB_SUMMARY\]' "$game_log" 2>/dev/null; then
    echo "GCB_SUITE_FINISHED" | tee -a "$runtime_log"
    for _ in $(seq 1 10); do
      pgrep -x isaac.x64 >/dev/null 2>&1 || exit 0
      sleep 1
    done
    pkill -TERM -x isaac.x64 >/dev/null 2>&1 || true
    exit 0
  fi
  pgrep -x isaac.x64 >/dev/null 2>&1 || exit 0
  sleep 1
done

echo "GCB_RUNTIME_INVALID suite_finish_timeout" | tee -a "$runtime_log"
exit 13
