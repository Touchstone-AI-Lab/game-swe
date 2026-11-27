# E0 notes: l4d2-infected-bots-release-regressions-medium

Workspace layout: `/app/l4d1_2_plugins`; every overlay uses `root = l4d1_2_plugins` and
patches `l4dinfectedbots/scripting/l4dinfectedbots.sp` (the only file the oracle changes).
The exam has no report ids; clause ids are `Contract-<item>.<n>` for the four numbered
contracts, `Intro-1` and `Keep-*` for the surrounding prose (anchors quote the sentence).

## Preserved contracts (all `P` in the unchanged starter)

| case | public statement |
| --- | --- |
| `capacity_unclamped_request_is_preserved` | Contract 1 s3: applied value visible through `GetConfigInt("max_specials")` |
| `config_settings_count_profile_overlays_all_types` | Contract 2 s1, s3, s4, s6 (Settings default + count entry, no map entry, cvar load, all three types) |
| `config_settings_count_omitted_keys_inherit_default` | Contract 2 s1b: omitted count keys inherit `Settings/default` |
| `config_admin_overrides_are_temporary` | Contract 2 s5 (override half only) |
| `initial_timer_eventually_replenishes` | Contract 3: the deferred replacement does arrive |
| `initial_timer_normal_delay_resumes_after_window` (overlap) | Contract 3 s2/s3b: normal delay after the window |

Sentinel/setup cases: `package_complete_public_source` and `submitted_plugins_compile`
(file/compile gates reported as cases), the four `*_loaded`/`*_guard` fixtures,
`initial_timer_victim_created` and `finale_win_event_available`.

## Controls

- `tn-predicate-capacity-only` (target-negative, starter + patch): the pack's own
  `validation/candidates/predicate-capacity.patch`. Only the `a/environment/l4d1_2_plugins/`
  path prefix in the three header lines was re-rooted to `a/` so that `patch -p1` applies from
  `/app/l4d1_2_plugins`; hunks are unchanged. Config, initial-window and finale defects remain.
- `tn-initial-window-unfixed` (target-negative, reference + patch): removes the `else` that the
  oracle adds after `if(g_bInitialSpawn) SpawnTime = ...` in the versus branch, restoring the
  Contract-3 defect only.
- `cn-settings-count-inheritance-lost` (compat-negative, reference + 1-line patch): the
  Settings count profile reads `spawn_time_max` with a hard-coded default `60.0` instead of
  inheriting `Settings/default`. The Maps stage is untouched, so the reload target (which
  inherits from the map default) still passes; only
  `config_settings_count_omitted_keys_inherit_default` is expected to fail.
- `alternative-a`, `alternative-b` (alternative, starter + patch): the pack's two complete
  non-oracle candidates, same header re-rooting as above, hunks unchanged.

## Exclusions / remarks

- No unasserted public clause. Weak clauses: `Contract-2.2` (one omitted key), `Contract-3.1`,
  `Contract-3.2`, `Contract-4.1` (single wall-clock samples; versus branch only).
- The timing cases are wall-clock samples in a real server; a control that changes scheduling
  could be flaky. None of the controls above depends on a timing margin except
  `tn-initial-window-unfixed`, whose failure mode (replacement after ~1 s instead of 8 s, sampled
  at 2.2 s) has a wide margin.
- No task-level exclusion recommended.

## Results (managed real L4D2 server, full profile)

All five controls are admissible (`problems: []`): `tn-predicate-capacity-only` fails the three
remaining targets, `tn-initial-window-unfixed` fails only
`initial_timer_not_overwritten_by_normal_delay`, `cn-settings-count-inheritance-lost` fails only
`config_settings_count_omitted_keys_inherit_default`, both alternatives pass 18/18 plus the
static check. Nothing was left unrun.
