# E0 notes: l4d2-left4dhooks-api-regressions-medium

Workspace layout: `/app/left4dhooks`; every overlay uses `root = left4dhooks` and patches files
below `sourcemod/scripting/`. Clause ids are the exam's report ids with a sentence suffix
(`LH-204.1` ...), plus `Task-*` for the Task section.

## Roles that differ from `validation/case-contracts.tsv`

The verifier fails a whole server boot closed when a fatal-looking line appears before FINAL.
In the unchanged starter this happens in the campaign-score, melee-info and lobby-reservation
boots, so seven cases labelled `guard` by the pack FAIL there:
`runtime_campaign_scores_library_loaded`, `campaign_scores_pre_forward_once`,
`campaign_scores_pre_receives_original_values`, `runtime_melee_info_library_loaded`,
`runtime_lobby_reservation_library_loaded`, `full_lobby_cookie_roundtrips`,
`lobby_cookie_can_be_restored`. A case that fails in the starter cannot be preserved (or
sentinel) evidence: its outcome is decided by the boot-level fatal scan, i.e. by the target
defect of that boot (`LH-264.3`, `LH-271.4`, `LH-298.1`). All seven are mapped `target` with
`overlap: true` and a note. The first run of `tn-predicate-ammo-only` showed why this matters:
with the three `runtime_*` cases mapped as sentinels, every tree that leaves those reports
unrepaired "fails cases outside the target set".

## Preserved contracts (20 cases, all `P` in the starter)

Stated in the same report as the target they guard: `LH-204.4/.5` (other `Ammo_t` state),
`LH-219.2/.4` (Molotov family), `LH-237.4` (adjacent player state), `LH-246.1/.3` (ordinary
float attributes, adjacent power), `LH-251.1/.3/.4` (two-client hooks, peer, final disable),
`LH-258.1/.2` (real pipe-bomb pairs, real break lifecycle), `LH-278.0/.3` (ordinary staggers),
`LH-284.3/.4` (ordinary prop, weapon gas-can path), `LH-291.2/.3` (stable lookups, null address).

## Controls

- `tn-predicate-ammo-only` (target-negative, starter + patch): byte-identical copy of
  `validation/candidates/predicate-ammo.patch`; only LH-204 is repaired.
- `tn-stagger-unfixed` (target-negative, reference + patch): the three LH-278 hunks of
  `l4dd_natives.sp` are put back to the starter text; everything else is the oracle.
- `cn-gascan-model-filter-removed` (compat-negative, reference + patch): the new
  `CPhysicsProp::OnTakeDamage` pre/post detours lose their `m_nModelIndex != g_iGasCanModel`
  early return, so every damaged physics prop dispatches the gas-can family. The unpicked gas-can
  targets are unaffected; `ordinary_physics_prop_never_dispatches_gascan_family` must fail.
- `cn-float-attributes-all-integral` (compat-negative, reference + patch):
  `L4D2_SetFloatWeaponAttribute` floors every attribute instead of only
  `L4D2FWA_PenetrationNumLayers`. The 3.75 -> 3.0 target still holds; ordinary decimal
  attributes (`ordinary_float_weapon_attribute_roundtrips`,
  `penetration_layers_preserve_adjacent_power`) break.
- `alternative-a`, `alternative-b` (alternative, starter + patch): byte-identical copies of the
  pack's two calibrated independent solutions.

## Exclusions / remarks

- Unasserted (excluded) clauses: `LH-284.5` (gas-can blocking/change semantics),
  `LH-291.4` (no side effects), `LH-291.5` (prescribed decoding strategy),
  `Task-preserve-unrelated-api`, `Task-preserve-l4d1`, `Task-no-tests-edit`.
- `LH-237.6` (documentation must match) is measured by a keyword scan that is both weak and
  over-constraining (`known_issues`). Recommend excluding clause `LH-237.6` / case
  `spawn_timer_documentation_describes_absolute_value` from contract-level conclusions; it
  does not justify excluding the task.

## Results (managed real L4D2 server, full profile)

All six controls are admissible (`problems: []`) under the final map:
`tn-predicate-ammo-only` fails 39 target cases and nothing else, `tn-stagger-unfixed` fails only
the two LH-278 targets, `cn-gascan-model-filter-removed` fails only
`ordinary_physics_prop_never_dispatches_gascan_family`, `cn-float-attributes-all-integral` fails
`ordinary_float_weapon_attribute_roundtrips` and `penetration_layers_preserve_adjacent_power`,
both alternatives pass 72/72 plus the static check. Nothing was left unrun.
