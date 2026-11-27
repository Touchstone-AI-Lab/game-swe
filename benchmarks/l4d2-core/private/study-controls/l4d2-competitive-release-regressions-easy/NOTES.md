# E0 notes: l4d2-competitive-release-regressions-easy

Workspace layout: `/app/l4d2-competitive`; every overlay uses `root = l4d2-competitive`
and patches `addons/sourcemod/scripting/*.sp`.

## Preserved contracts (all `P` in the unchanged starter)

| case | public statement |
| --- | --- |
| `incap_loaded_clip_delays_secondary_attack` | [#CR-101] s1: shove suppression with ammunition still works |
| `incap_exit_releases_applied_delay` (overlap) | [#CR-101] s4a: leaving incap releases a delay the plugin applied |
| `incap_non_survivor_is_unchanged`, `incap_missing_active_weapon_is_safe` | [#CR-101] s4b: clients outside the Survivor/incap path unaffected |
| `attributes_outgoing_mode_changes_take_effect` | [#CR-118] s1 and Task "commands" |
| `attributes_manual_reset_command_remains_functional` | [#CR-118] s5: keep the manual reset command |
| `attributes_config_reload_behavior_is_preserved` | [#CR-118] s5: keep normal config-reload behavior |
| `changelevel_complete_name_still_works`, `changelevel_director_work_is_preserved_for_complete_name` | [#CR-126] s3 and Task "Director reset work" |
| `changelevel_invalid_name_is_not_rewritten` (overlap) | [#CR-126] s4 |

The three `*_loaded` cases are load sentinels; they additionally compare `myinfo`
strings (Task "plugin metadata").

## Controls

- `tn-incap-unfixed` (target-negative, reference + patch): puts the starter's
  `l4d2_incap_fire_fix.sp` logic back. CR-118 and CR-126 stay repaired. Observed:
  fails only `incap_empty_clip_leaves_reload_unblocked`.
- `tn-transition-early-return` (target-negative, reference + patch): keeps the FindMap
  resolution but places it after the `TheDirector.IsTransitioning()` early return, i.e. a
  repair that misses the CR-126 lifecycle condition. Observed: fails only
  `changelevel_partial_is_honored_while_transitioning`.
- `cn-config-reload-resets-managed` (compat-negative, reference + 3-line patch):
  `OnConfigsExecuted` calls the full `ResetAllAttributes(false)` instead of re-applying saved
  values. The unload-forward target still works; a normal config reload now discards ordinary
  values and the managed multipliers. Observed: every target passes, only
  `attributes_config_reload_behavior_is_preserved` fails.
- `alternative-restructured` (alternative, starter + patch): re-created from the two strategy
  rows of `validation/differential-matrix.tsv` (`guarded-incap`, `map-helper`) and extended to
  the third file so that no reference file is reused: guard-clause incap flow with
  `WeaponHasLoadedClip`/`ReleaseOwnedDelay` helpers; `ResolveInstalledMap` helper with a
  `switch` over `FindMapResult`; a dedicated `RestoreOwnedState` for
  `LGO_OnMatchModeUnloaded` instead of calling `ResetAllAttributes`. It uses `FindMap` like
  the reference because the maintainer notes record that `GetMapDisplayName` does not resolve
  `c1m2` on the pinned runtime. Observed: 20/20.

All four controls were executed in the managed real L4D2 server and are admissible
(`problems: []`).

## Exclusions / remarks

- Unasserted public clauses (excluded): `Task-preserve-forwards` (existing event/forward
  integration is not observed), `Task-preserve-gpl` (enforced only by a pre-case package gate in
  verify.py, not by a named case) and `Task-no-tests-edit` (process rule).
- No task-level exclusion recommended. Read results with the suite-level fail-closed rule in
  mind (see `known_issues` in the clause map): a runtime exception in one plugin fails all
  cases of that server boot, including preserved ones.

## Not run

Nothing outstanding for this task.
