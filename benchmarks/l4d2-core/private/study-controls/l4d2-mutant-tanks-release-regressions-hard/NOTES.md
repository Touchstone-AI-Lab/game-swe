# E0 notes: l4d2-mutant-tanks-release-regressions-hard

Workspace layout: `/app/mutant-tanks`; every overlay uses `root = mutant-tanks` and patches
files below `addons/sourcemod/scripting/mutant_tanks/`. The exam has numbered report sections
but no ids; clause ids are `R<report>.<n>` (anchor = report, sentence, short quote) and `Task-*`.

`rhenium-study e0 baseline` for the pack aborted at the preceding task (see the linge NOTES), so
the starter/reference baseline of this task was produced by running
`rhenium-study e0 baseline <this task>` separately: starter 32/57, reference 57/57.

## Roles that differ from `validation/case-contracts.tsv`

- `acid_melee_cooldown_recovers_after_expiry` and `ammo_melee_cooldown_recovers_after_expiry`
  are labelled `guard` but FAIL in the unchanged starter (three hits produce three effects, the
  cases expect exactly two). They are mapped `target` with `overlap: true`.
- `hypno_tank_removal_cleans_shield`, `rainbow_old_bot_stops_after_takeover` and
  `rainbow_old_player_stops_after_idle` are labelled `target` but already pass in the starter
  (no shield / no transferred animation exists there). They stay `target` with `overlap: true`:
  they are the "and nothing is left behind" half of the requested lifecycle.
- `health_smoker_mutation_completes` is a fixture (`setup`); the three `runtime_*` cases are load
  sentinels that also pin the plugin names (Task "plugin identity").

## Preserved contracts (25 cases, all `P` in the starter)

`R1.1`/`R1.2` (callback stream, ordinary entry), `R2.2` (explicit Tank-type SI health), `R3.2`
(unpinned Warp), `R5.2`-`R5.5` (the whole B-then-A order, old-owner reset, expiry, first
reward), `R6.4` (View=0 gameplay hit), `R7.2` (explicit Panic mask), `R8.1` (animation before
handoff), `R9.3` (zero cooldown).

## Controls

- `tn-predicate-warp-only` (target-negative, starter + patch): byte-identical copy of
  `validation/candidates/predicate-warp.patch`; only Report 3 is repaired.
- `tn-panic-fallback-unfixed` (target-negative, reference + patch): `mt_panic.sp` is put back to
  the starter; Report 7 is unrepaired, everything else is the oracle.
- `cn-reward-stack-keeps-first` (compat-negative, reference + 2-line patch): both oracle stack
  helpers keep the active value when a later smaller reward arrives instead of adding it. This is
  exactly the over-fix the public text warns about ("do not make all repeated rewards simply keep
  the first value"): the A-then-B targets (15 damage / 10 rounds) still hold, the preserved
  B-then-A order (35 / 30) breaks.
- `alternative-a`, `alternative-b` (alternative, starter + patch): byte-identical copies of the
  pack's two complete non-oracle candidates.

## Exclusions / remarks

- Unasserted (excluded) clauses: `Task-preserve-gpl` (pre-case package gate only),
  `Task-no-unrelated`, `Task-no-tests-edit`.
- Every boot is failed closed on a SourceMod exception; the starter logs exceptions of its own,
  so per-case starter outcomes partly reflect that rule rather than the named assertion.
- No task-level exclusion recommended.

## Results (managed real L4D2 server, full profile)

All five controls are admissible (`problems: []`): `tn-predicate-warp-only` fails 21 target
cases and nothing else, `tn-panic-fallback-unfixed` fails only the two Report 7 targets,
`cn-reward-stack-keeps-first` passes every target and fails four preserved B-then-A cases
(stacked damage/ammo before and after the handoff), both alternatives pass 57/57 plus the static
check. Nothing was left unrun.
