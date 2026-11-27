# E0 notes: l4d2-linge-release-regressions-hard-v3

Workspace layout: `/app/linge-hud`; every overlay uses `root = linge-hud` and patches
`vscripts/LinGe/{HUD,Hint,RewardHP}.nut`. Clause ids: the exam's `LG-4xx` ids with a sentence
suffix, `LG-PRES.n` for the block the exam labels `[Preservation: delayed team-hurt messages.]`,
and `Task-*` for the Task section. `case-contracts.tsv` uses the `class`/`defect_group` layout.

## Tooling problem: the implicit `reference` cannot be built

`solution/solve.sh` delegates to `solution/solve.py`, which hard-codes
`ROOT = /app/linge-hud/...` (solve.py:5). `rhenium_study.controls._apply_reference`
(controls.py:88-102) relocates `/app` and `/solution` only in the text of solve.sh, so the
oracle fails with `FileNotFoundError` outside a container. Consequences:

- `rhenium-study e0 baseline` aborted at this task: there is a `starter.execution.json` but no
  `reference.execution.json`, and `rhenium-study e0 run <task>` without `--only` aborts as well.
- Every control here is `base = starter` with a complete patch (oracle changes + the control's
  own change). `reference-equivalent.patch` is the oracle tree as a patch (built by running
  solve.py with ROOT pointed at a scratch copy; byte-identical to `solution/after/.../HUD.nut`
  plus the two solve.py replacements). It is NOT listed in `manifest.tsv`; it was executed once
  through a temporary manifest row as evidence that the oracle resolves under the study runtime:
  record `e0/records/left-4-dead-2/core/<task>/reference-equivalent.json`, 43/43 `P`
  (run-a8f5b4dc0c4f4533). The clause map's case list was checked against that run.
- Fixing this needs a change outside `study-controls/` (tool or oracle), which this task does
  not allow.

## Preserved contracts (28 cases, all `P` in the unchanged starter)

- `LG-PRES.1`-`.4` (the explicit preservation block): pair aggregation, independent pairs,
  self-damage, already incapacitated/dying/dead.
- `LG-417.0`, `Task-preserve-ordinary-damage`, `Task-preserve-kill-counters`: ordinary
  friendly fire, Tank, SI damage, zero-type and invalid/non-Survivor attackers, kill/headshot
  counters.
- Boundaries stated inside the reports, marked `overlap: true`: temporary health on a
  non-terminal hit, stale negative-health events, self-incapacitation, Tank terminal event
  without a valid attacker, non-Tank incapacitation, non-qualified flame combinations
  (`LG-433.2`), SI terminal clamp (`LG-433.3`), RewardHP mode 2 full reward and mode 3 fallback
  (`LG-452.1/.2`).

There is no separate runtime sentinel: the suite is one server boot and reports nothing at all
unless the addon loads and the FINAL marker is unique.

## Controls (all executed in the real server VM; all admissible)

- `tn-hint-lifecycle-unfixed` (target-negative): oracle HUD/RewardHP, starter `Hint.nut`
  (`DOMINATE = 0` makes REVIVE collide with DOMINATE). Fails exactly the two LG-445 targets.
- `tn-rewardhp-unfixed` (target-negative): oracle HUD/Hint, starter `RewardHP.nut`. Fails exactly
  `rewardhp-temporary-only-mode-clamps-at-limit`.
- `cn-flame-scale-ignores-type` (compat-negative): oracle tree, but the x3 entityflame
  normalization drops the `params.type == 268435464` condition. The LG-433.1 target still
  passes; only `ordinary-entityflame-type-is-not-multiplied` fails.
- `cn-hybrid-mode-clamped` (compat-negative): oracle tree, but the mode-2 clamp branch is entered
  for every mode other than 1, so mode 3 loses its permanent fallback. The LG-452.1 target still
  passes; only `rewardhp-hybrid-mode-preserves-permanent-fallback` fails.
- `alternative-snapshot-transition` (alternative, new): re-created from the strategy rows of
  `validation/differential-matrix.tsv` (candidate-1 VSLib pre-damage snapshot, candidate-2
  death-event exact-zero fallback, candidate-3 map_transition baseline, candidate-4 separate
  lifecycle values), combined in one tree that shares no repaired code with the oracle:
  Tank terminal health comes from a `VSLib.EasyLogic.OnTakeDamage` snapshot consumed by
  `player_hurt` (the oracle uses `player_incapacitated` and a type filter); Survivor accounting
  goes through one `RecordTeamHurt` helper used by `player_hurt` and
  `player_incapacitated_start`; the exact-zero label is set by the `player_death` fallback while
  `player_hurt` keeps a strict negative check; SI scaling is a weapon/type lookup table; the
  rollback baseline advances in the `map_transition` handler, not in `cache_restore`; `HINTMODE`
  is numbered explicitly instead of removing `= 0`; RewardHP computes the remaining room once
  and returns early in mode 2. Passed 43/43 on its first run; it was not tuned against the suite.

The historical "crash at case 28" did not occur for any control; no case was unobserved.

## Exclusions / remarks

- Unasserted (excluded) clauses: `Task-preserve-ranking-cache-config`, `Task-no-polling`,
  `Task-license` (pre-case package gate only, no named case), `Task-no-tests-edit`.
- `LG-433.1` is asserted but over-constrained towards the x3 rule (see `known_issues`): a
  submission that measures real health loss from observed health fails it. Keep the clause, but
  read a lone failure of `qualified-entityflame-tick-uses-real-health-loss` with that in mind.
- All HUD/RewardHP cases run against Squirrel mock players inside the real VM; they are
  handler-arithmetic evidence, not engine-damage evidence.
