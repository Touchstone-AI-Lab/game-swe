#!/usr/bin/env bash
set -uo pipefail

logs=/logs/verifier
data_dir="/home/azureuser/.local/share/binding of isaac afterbirth+"
mods_dir="/home/azureuser/.local/share/binding of isaac afterbirth+ mods"
game_log="$data_dir/log.txt"
submission_mod="$mods_dir/gcb_construct_room_rng_submission"
suite_mod="$mods_dir/gcb_construct_room_rng_suite"
expected=35
expected_cases=(
  same_run_room_same_sequence
  different_room_distinct_stream
  different_run_distinct_stream
  same_room_reload_same_stream
  save_resume_next_value
  save_resume_consumed_count
  new_run_resets_derived_state
  room_entry_reseeds_only_room_stream
  update_draw_order_stable
  room_seed_not_global_rng
  no_global_rng_reseed
  no_global_rng_consumption
  game_rng_unchanged_by_first_draw
  repeated_update_advances_once
  duplicate_room_callback_idempotent
  room_reentry_resumes_saved_stream
  visited_room_state_isolated
  unvisited_room_state_deterministic
  state_round_trip
  malformed_persisted_state_recovers
  missing_persisted_state_initializes
  run_seed_is_part_of_key
  room_spawn_seed_is_part_of_key
  value_range_is_inclusive
  integer_generation_is_stable
  no_callback_order_drift
  save_callback_does_not_advance
  game_start_callback_resets_once
  room_change_does_not_reset_run
  save_after_n_draws_resumes_n_plus_one
  invalid_room_entry_isolated
  stream_state_does_not_alias
  no_math_random_dependency
  room_stream_cached_not_reinitialized
  zero_seed_normalizes_to_one
)

install -d -m 0755 "$logs" "$mods_dir" /tmp/.X11-unix
chmod 1777 /tmp/.X11-unix
truncate -s 0 "$logs/runtime.log"
chown 1000:1000 "$logs" "$logs/runtime.log"

if [ ! -f /app/exodus/main.lua ] || [ ! -f /app/exodus/metadata.xml ]; then
  echo "0" >"$logs/reward.txt"
  echo "INVALID_ARTIFACT missing /app/exodus mod source"
  exit 0
fi
if [ ! -f /tests/suite/main.lua ] || [ ! -f /tests/suite/metadata.xml ]; then
  echo "0" >"$logs/reward.txt"
  echo "INVALID_ARTIFACT missing verifier suite"
  exit 0
fi

rm -rf "$submission_mod" "$suite_mod"
cp -a /app/exodus "$submission_mod"
cp -a /tests/suite "$suite_mod"
chown -R 1000:1000 "$submission_mod" "$suite_mod" "$data_dir" "$mods_dir"

if grep -q '^EnableMods=' "$data_dir/options.ini"; then
  sed -i -E 's/^EnableMods=.*/EnableMods=1/' "$data_dir/options.ini"
else
  printf '\nEnableMods=1\n' >>"$data_dir/options.ini"
fi
if grep -q '^SteamCloud=' "$data_dir/options.ini"; then
  sed -i -E 's/^SteamCloud=.*/SteamCloud=0/' "$data_dir/options.ini"
else
  printf '\nSteamCloud=0\n' >>"$data_dir/options.ini"
fi
chown 1000:1000 "$data_dir/options.ini"

# Each evaluation starts with a fresh run; the verifier only writes mod data.
find "$data_dir" -maxdepth 1 -type f -name 'abp_gamestate*.dat' -delete
find /home/azureuser/.steam/debian-installation/userdata \
  -path '*/250900/remote/abp_gamestate*.dat' -type f -delete 2>/dev/null || true
truncate -s 0 "$game_log"
chown 1000:1000 "$game_log"

runuser -u azureuser -- /tests/run-game.sh
runtime_status=$?
sed 's/\x1b\[[0-9;]*m//g' "$game_log" >"$logs/game.log"

passed=$(grep -c '\[GCB_CASE\] PASS ' "$logs/game.log" 2>/dev/null || true)
failed=$(grep -c '\[GCB_CASE\] FAIL ' "$logs/game.log" 2>/dev/null || true)
summaries=$(grep -c '\[GCB_SUMMARY\] passed=35 failed=0 total=35' \
  "$logs/game.log" 2>/dev/null || true)
fatals=$(grep -c '\[GCB_FATAL\]' "$logs/game.log" 2>/dev/null || true)
case_occurrences_ok=1
case_counts=""
for case_name in "${expected_cases[@]}"; do
  case_count=$(grep -c "\[GCB_CASE\] PASS ${case_name} " \
    "$logs/game.log" 2>/dev/null || true)
  case_counts="${case_counts}${case_name}=${case_count},"
  if [ "$case_count" -ne 1 ]; then
    case_occurrences_ok=0
  fi
done

if [ "$runtime_status" -ne 0 ]; then
  echo "0" >"$logs/reward.txt"
  echo "runtime_exit=$runtime_status passed=$passed failed=$failed INVALID_RUNTIME"
  exit 0
fi
if [ "$passed" -eq "$expected" ] \
  && [ "$failed" -eq 0 ] \
  && [ "$summaries" -eq 1 ] \
  && [ "$fatals" -eq 0 ] \
  && [ "$case_occurrences_ok" -eq 1 ]; then
  echo "1" >"$logs/reward.txt"
else
  echo "0" >"$logs/reward.txt"
fi

echo "runtime_exit=$runtime_status passed=$passed failed=$failed expected=$expected summaries=$summaries fatals=$fatals case_occurrences_ok=$case_occurrences_ok cases=$case_counts"
exit 0
