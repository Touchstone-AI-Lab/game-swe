#!/usr/bin/env bash
set -uo pipefail

logs=/logs/verifier
data_dir="/home/azureuser/.local/share/binding of isaac afterbirth+"
mods_dir="/home/azureuser/.local/share/binding of isaac afterbirth+ mods"
game_log="$data_dir/log.txt"
submission_mod="$mods_dir/gcb_construct_entity_cleanup_submission"
suite_mod="$mods_dir/gcb_construct_entity_cleanup_suite"
expected=35
expected_cases=(
  created_effect_is_tracked
  foreign_entity_is_not_tracked
  live_owner_keeps_effect
  dead_owner_removes_effect
  removed_owner_removes_effect
  owner_missing_clears_reference
  room_change_removes_old_owned_effect
  room_change_keeps_foreign_effect
  reentry_does_not_restore_old_owner
  repeated_cleanup_is_idempotent
  duplicate_remove_callback_is_safe
  already_removed_entity_is_safe
  nil_owner_is_safe
  effect_removed_once
  registry_entry_removed_once
  reused_entity_index_not_reused
  ownership_token_matches_entity
  ownership_token_survives_update
  ownership_token_cleared_on_room_change
  new_owner_does_not_adopt_stale_effect
  two_owners_clean_independently
  multiple_effects_per_owner_clean
  foreign_sibling_effect_survives_cleanup
  entity_removed_callback_scoped
  partial_effect_remove_clears_only_one
  post_update_catches_missing_remove_event
  room_identity_prevents_cross_room_cleanup
  cleanup_order_does_not_skip_entries
  cleanup_after_owner_death
  cleanup_after_owner_remove
  cleanup_after_transition_then_remove
  no_double_free_on_transition
  foreign_entity_untouched_on_bulk_scan
  registry_empty_after_all_owners_removed
  reused_index_does_not_adopt_new_entity
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
