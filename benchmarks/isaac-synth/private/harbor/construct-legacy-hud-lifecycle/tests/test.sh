#!/usr/bin/env bash
set -uo pipefail

logs=/logs/verifier
data_dir="/home/azureuser/.local/share/binding of isaac afterbirth+"
mods_dir="/home/azureuser/.local/share/binding of isaac afterbirth+ mods"
game_log="$data_dir/log.txt"
submission_mod="$mods_dir/gcb_construct_legacy_hud_lifecycle_submission"
suite_mod="$mods_dir/gcb_construct_legacy_hud_lifecycle_suite"
expected=35
expected_cases=(
  version2_saves_all_categories
  general_value_round_trip
  partial_load_defaults
  legacy_flat_menu_migrates
  legacy_migration_saves_v2
  missing_options_default_zero
  offset_clamped_low
  offset_clamped_high
  seed_absent_initially
  menu_open_adds_seed_only_when_absent
  preexisting_seed_preserved
  menu_close_removes_owned_seed
  menu_close_preserves_preexisting_seed
  repeated_open_idempotent
  repeated_close_idempotent
  hud_offset_nil_fallback
  hud_offset_non_numeric_fallback
  hud_offset_finite_clamp
  options_root_absent_safe
  unsupported_apis_never_used
  load_callback_does_not_throw
  render_callback_does_not_throw
  load_decoded_table_merges
  missing_fields_default
  invalid_category_default
  unknown_keys_ignored
  malformed_json_defaults
  non_table_json_defaults
  hasdata_false_defaults
  missing_data_defaults
  save_after_load_is_v2
  save_does_not_mutate_live_config
  continued_load_restores_config_and_open_effect
  new_run_uses_defaults
  seed_restored_after_room_change
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
