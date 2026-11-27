#!/bin/bash
# Second and last approved diagnostic: no raw stderr, screen or input capture.
set -euo pipefail
umask 077
[[ $# == 0 && "$HOME" == /home/steamprobe && "$(id -u)" == 1000 ]]
[[ "$DISPLAY" == :0 ]]
client="$HOME/.steam/debian-installation"
[[ -f "$HOME/probe-launch-started" && ! -e "$HOME/probe-diagnostic-2-started" ]]
[[ ! -e "$client/ubuntu12_64/steamwebhelper.sh" && ! -e "$client/config/loginusers.vdf" ]]
touch "$HOME/probe-diagnostic-2-started"
install -d -m 0700 "$XDG_RUNTIME_DIR"
printf 'stage=bounded_update_diagnostic_start\n'
# Only fixed, deduplicated classifications reach container output. No client
# line, account name, token, prompt, or arbitrary substring is emitted or stored.
# This does not turn an incomplete update or authentication into success.
timeout --signal=TERM --kill-after=15s 900s \
  dbus-run-session -- "$client/steam.sh" -console >/dev/null 2> >(
  awk '
    function emit(key) { if (!seen[key]++) { print "class=" key; fflush(); } }
    { s = tolower($0) }
    s ~ /error while loading shared libraries/ { emit("missing_shared_library") }
    s ~ /cannot open display|unable to open.*display|cannot connect.*display/ { emit("display_connection") }
    s ~ /xio:|x error|badalloc|badvalue/ { emit("x11_error") }
    s ~ /operation not permitted/ { emit("operation_not_permitted") }
    s ~ /permission denied/ { emit("permission_denied") }
    s ~ /no space left/ { emit("no_space") }
    s ~ /segmentation fault|sigsegv/ { emit("segmentation_fault") }
    s ~ /core dumped/ { emit("core_dump") }
    s ~ /cannot allocate memory|out of memory/ { emit("allocation_failure") }
    s ~ /failed to create.*thread|resource temporarily unavailable/ { emit("thread_or_resource_limit") }
    s ~ /sandbox|bwrap|unshare/ { emit("sandbox_runtime_message") }
    s ~ /timed out/ { emit("timeout_message") }
    s ~ /fatal/ { emit("fatal_message") }
    s ~ /assert/ { emit("assertion_message") }
    s ~ /crash/ { emit("crash_message") }
    s ~ /error/ { emit("error_message") }
    s ~ /restarting steam by request/ { emit("client_requested_restart") }
  '
)
