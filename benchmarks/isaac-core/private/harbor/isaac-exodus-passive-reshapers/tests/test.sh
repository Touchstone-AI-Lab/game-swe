#!/usr/bin/env bash
set -uo pipefail

logs=/logs/verifier
data_dir="/home/azureuser/.local/share/binding of isaac afterbirth+"
mods_dir="/home/azureuser/.local/share/binding of isaac afterbirth+ mods"
game_log="$data_dir/log.txt"
submission_mod="$mods_dir/gcb_exodus_submission"
suite_mod="$mods_dir/gcb_exodus_suite"
expected=54
expected_cases=(
  runtime_sentinel_main
  runtime_sentinel_secret
  runtime_sentinel_james
  forbidden_fruit
  tragic_mushroom
  tragic_mushroom_last_container
  tragic_mushroom_repeat
  tragic_mushroom_diminishing
  mutant_clover_stack
  mutant_clover_room_reset
  anamnesis_charge
  anamnesis_charge_persistence
  baseball_mitt_delayed_hit
  iron_lung_orphan_gas
  headcase_orphan_lob
  ritual_candle
  ritual_candle_cadence
  familiar_cleanup
  beehive_early_wobble
  beehive_mature_wobble
  deja_vu_split_guard
  deja_vu_normal_return
  lil_rune_jera_health
  lovely_fly_target
  grid_worm
  grid_worm_heading
  grid_worm_heading_cross_axis
  grid_worm_bounce
  grid_worm_cadence_regression
  blue_moon
  apocryphon_stats
  broken_glasses
  broken_glasses_floor_reset
  james_book_of_secrets_scope
  james_book_of_secrets_positive
  cursed_metronome
  hurdle_heels_landing_stomp
  hurdle_heels_player_protected
  ominous_lantern_put_away
  ominous_lantern_throw_recharge
  childs_leash_orbitals
  lil_rune_algiz_rune
  big_scissors_trail
  unholy_mantle_burst
  unholy_mantle_once
  birdbath_use_spawns
  paper_cut_card_damage
  baseball_mitt_return_flags
  welcome_mat_poof_at_rest
  welcome_mat_flame_at_rest
  welcome_mat_bonus_kept
  welcome_mat_floor_start
  welcome_mat_next_room
  new_run_starts_with_base_stats
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

# These exact directories exist only in this disposable verifier container.
rm -rf "$submission_mod" "$suite_mod"
cp -a /app/exodus "$submission_mod"
chown -R 1000:1000 "$submission_mod" "$data_dir" "$mods_dir"

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

run_suite() {
  local suite_source=$1
  local output_log=$2

  rm -rf "$suite_mod"
  cp -a "$suite_source" "$suite_mod"
  chown -R 1000:1000 "$suite_mod"

  # Remove ordinary run saves while retaining unlock data required by Exodus.
  # Steam can still offer the just-finished run from its in-memory cache, so the
  # broad main suite runs first and the self-isolating room suite runs second.
  find "$data_dir" -maxdepth 1 -type f -name 'abp_gamestate*.dat' -delete
  find /home/azureuser/.steam/debian-installation/userdata -path '*/250900/remote/abp_gamestate*.dat' \
    -type f -delete 2>/dev/null || true
  truncate -s 0 "$game_log"
  chown 1000:1000 "$game_log"

  runuser -u azureuser -- /tests/run-game.sh
  local status=$?
  sed 's/\x1b\[[0-9;]*m//g' "$game_log" >"$output_log"
  return "$status"
}

secret_log="$logs/game-secret-room.log"
main_log="$logs/game-main.log"
james_log="$logs/game-james.log"
run_suite /tests/suite "$main_log"
main_status=$?
run_suite /tests/james-suite "$james_log"
james_status=$?
run_suite /tests/secret-suite "$secret_log"
secret_status=$?

runtime_status=0
if [ "$secret_status" -ne 0 ]; then
  runtime_status=$secret_status
elif [ "$james_status" -ne 0 ]; then
  runtime_status=$james_status
elif [ "$main_status" -ne 0 ]; then
  runtime_status=$main_status
fi

clean_log="$logs/game.log"
sed -n 'p' "$secret_log" >"$clean_log"
sed -n 'p' "$james_log" >>"$clean_log"
sed -n 'p' "$main_log" >>"$clean_log"
passed=$(grep -c '\[GCB_CASE\] PASS ' "$clean_log" 2>/dev/null || true)
failed=$(grep -c '\[GCB_CASE\] FAIL ' "$clean_log" 2>/dev/null || true)
secret_summaries=$(grep -c '\[GCB_SUMMARY\] passed=3 failed=0 total=3' "$secret_log" 2>/dev/null || true)
james_summaries=$(grep -c '\[GCB_SUMMARY\] passed=2 failed=0 total=2' "$james_log" 2>/dev/null || true)
main_summaries=$(grep -c '\[GCB_SUMMARY\] passed=49 failed=0 total=49' "$main_log" 2>/dev/null || true)
summaries=$((secret_summaries + james_summaries + main_summaries))
fatals=$(grep -c '\[GCB_FATAL\]' "$clean_log" 2>/dev/null || true)
case_occurrences_ok=1
case_counts=""
for case_name in "${expected_cases[@]}"; do
  case_count=$(grep -c "\[GCB_CASE\] PASS ${case_name} " "$clean_log" 2>/dev/null || true)
  case_counts="${case_counts}${case_name}=${case_count},"
  if [ "$case_count" -ne 1 ]; then
    case_occurrences_ok=0
  fi
done

if [ "$runtime_status" -ne 0 ]; then
  echo "0" >"$logs/reward.txt"
  echo "runtime_exit=$runtime_status secret_exit=$secret_status james_exit=$james_status main_exit=$main_status passed=$passed failed=$failed INVALID_RUNTIME"
  exit 0
fi

if [ $((passed + failed)) -eq 0 ]; then
  echo "0" >"$logs/reward.txt"
  echo "runtime_exit=0 passed=0 failed=0 INVALID_SUITE_DID_NOT_RUN"
  exit 0
fi

if [ "$passed" -eq "$expected" ] \
  && [ "$failed" -eq 0 ] \
  && [ "$secret_summaries" -eq 1 ] \
  && [ "$james_summaries" -eq 1 ] \
  && [ "$main_summaries" -eq 1 ] \
  && [ "$fatals" -eq 0 ] \
  && [ "$case_occurrences_ok" -eq 1 ]; then
  echo "1" >"$logs/reward.txt"
else
  echo "0" >"$logs/reward.txt"
fi

echo "runtime_exit=$runtime_status secret_exit=$secret_status james_exit=$james_status main_exit=$main_status passed=$passed failed=$failed expected=$expected summaries=$summaries fatals=$fatals case_occurrences_ok=$case_occurrences_ok cases=$case_counts"
exit 0
