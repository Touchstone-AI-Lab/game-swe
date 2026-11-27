#!/usr/bin/env bash
# Launch script of one construct verifier container. It is the launch-hardened script the
# derived Exodus tasks ship (client start, launch request retries and wall-clock budgets);
# the game is driven into a fresh run and the companion suite mod reports the cases.
set -uo pipefail

export HOME=/home/azureuser
export DISPLAY=:99
export LIBGL_ALWAYS_SOFTWARE=1
export GDK_BACKEND=x11
export SDL_VIDEODRIVER=x11
export XDG_RUNTIME_DIR=/tmp/steam-runtime-azureuser
export GTK_A11Y=none

steam="$HOME/.steam/debian-installation/steam.sh"
console_log="$HOME/.steam/debian-installation/logs/console_log.txt"
runtime_log=/logs/verifier/runtime.log
game_log="$HOME/.local/share/binding of isaac afterbirth+/log.txt"
launch_marker="'-applaunch' '250900'"
xvfb_pid=""
openbox_pid=""

steam_running() {
  pgrep -x steam >/dev/null 2>&1
}

# Occurrences of a fixed string in the client's console log (0 when it does not exist).
console_count() {
  local count
  count=$(grep -cF -- "$1" "$console_log" 2>/dev/null) || true
  echo "${count:-0}"
}

# Remove every process of the client. `steam.sh -shutdown` is not used for a client that
# does not take commands: it only queues, and with no client left it starts a new one.
kill_client() {
  pkill -KILL -u "$(id -u)" -f 'steam|pressure-vessel|srt-|pv-adverb|reaper|dbus-' >/dev/null 2>&1 || true
  for _ in $(seq 1 30); do
    steam_running || break
    sleep 1
  done
  rm -f "$HOME/.steam/steam.pid" "$HOME/.steam/steam.pipe"
}

# Ask a working client to exit and remove whatever is left of it after 60 seconds.
# Invoked indirectly by the EXIT trap below.
# shellcheck disable=SC2317,SC2329
stop_client() {
  if steam_running; then
    "$steam" -shutdown >>"$runtime_log" 2>&1 || true
    for _ in $(seq 1 60); do
      steam_running || break
      sleep 1
    done
  fi
  if steam_running; then
    echo "GCB_RUNTIME_NOTE steam_client_killed" | tee -a "$runtime_log"
    kill_client
  fi
}

# Invoked indirectly by the EXIT trap below.
# shellcheck disable=SC2317,SC2329
shutdown_runtime() {
  stop_client
  [ -z "$openbox_pid" ] || kill "$openbox_pid" >/dev/null 2>&1 || true
  [ -z "$xvfb_pid" ] || kill "$xvfb_pid" >/dev/null 2>&1 || true
}
trap shutdown_runtime EXIT

# Forward a launch request to the running client. It runs in the background because the
# forwarding steam.sh can itself take a minute on a slow disk, and it is skipped without a
# client because steam.sh would then start a second one.
request_launch() {
  steam_running || return 0
  "$steam" -applaunch 250900 >>"$runtime_log" 2>&1 &
}

# Wait for the game process once the client has taken a launch request.
game_process() {
  for _ in $(seq 1 240); do
    pgrep -x isaac.x64 >/dev/null 2>&1 && return 0
    sleep 1
  done
  return 1
}

# One client start. Returns 0 once the game process exists, 10 when no client process
# appears, and 1 when this client did not start the game.
#
# A launch request forwarded while the bootstrapper still verifies or updates itself is
# dropped. One forwarded after the client proper is up is queued and taken when its
# startup finishes, so the request is sent as soon as the client logs its version. A
# request that arrives after startup is ignored by a client whose UI thread has wedged,
# so an ignored request is repeated once and then the client is replaced.
launch_attempt() {
  local versions startups launches now
  versions=$(console_count 'Client version:')
  startups=$(console_count 'System startup time')
  launches=$(console_count "$launch_marker")
  dbus-run-session -- "$steam" \
    -silent -offline -cef-disable-gpu -cef-force-opaque-backgrounds -no-cef-sandbox \
    >>"$runtime_log" 2>&1 &
  for _ in $(seq 1 90); do
    steam_running && break
    sleep 1
  done
  steam_running || return 10
  for _ in $(seq 1 420); do
    now=$(console_count 'Client version:')
    [ "$now" -ge "$versions" ] || versions=0
    [ "$now" -gt "$versions" ] && break
    steam_running || return 1
    sleep 1
  done
  request_launch
  for _ in $(seq 1 420); do
    now=$(console_count 'System startup time')
    [ "$now" -ge "$startups" ] || startups=0
    [ "$now" -gt "$startups" ] && break
    pgrep -x isaac.x64 >/dev/null 2>&1 && return 0
    steam_running || return 1
    sleep 1
  done
  for request in 1 2; do
    for _ in $(seq 1 60); do
      pgrep -x isaac.x64 >/dev/null 2>&1 && return 0
      now=$(console_count "$launch_marker")
      [ "$now" -ge "$launches" ] || launches=0
      if [ "$now" -gt "$launches" ]; then
        game_process
        return
      fi
      steam_running || return 1
      sleep 1
    done
    echo "GCB_RUNTIME_NOTE launch_request_ignored request=$request" | tee -a "$runtime_log"
    [ "$request" -eq 2 ] || request_launch
  done
  return 1
}

install -d -m 0700 "$XDG_RUNTIME_DIR"
Xvfb :99 -screen 0 1280x800x24 -nolisten tcp >>"$runtime_log" 2>&1 &
xvfb_pid=$!
for _ in $(seq 1 20); do
  xdotool getmouselocation >/dev/null 2>&1 && break
  sleep 1
done
openbox >>"$runtime_log" 2>&1 &
openbox_pid=$!

steam_started=0
game_started=0
for attempt in 1 2 3 4; do
  launch_attempt
  attempt_status=$?
  [ "$attempt_status" -eq 10 ] || steam_started=1
  if [ "$attempt_status" -eq 0 ]; then
    game_started=1
    break
  fi
  echo "GCB_RUNTIME_NOTE client_restart attempt=$attempt status=$attempt_status" | tee -a "$runtime_log"
  kill_client
done
if [ "$steam_started" -ne 1 ]; then
  echo "GCB_RUNTIME_INVALID steam_start_timeout" | tee -a "$runtime_log"
  exit 10
fi
if [ "$game_started" -ne 1 ]; then
  echo "GCB_RUNTIME_INVALID game_start_timeout" | tee -a "$runtime_log"
  exit 11
fi
echo "GCB_ISAAC_STARTED" | tee -a "$runtime_log"

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
for _ in $(seq 1 60); do
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

for _ in $(seq 1 900); do
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
