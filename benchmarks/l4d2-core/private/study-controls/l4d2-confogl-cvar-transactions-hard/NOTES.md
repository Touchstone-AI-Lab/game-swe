# E0 notes: l4d2-confogl-cvar-transactions-hard

Workspace layout: `/app/l4d2-competitive`; every overlay uses `root = l4d2-competitive`. Clause ids are `R<report>.<n>` for the numbered reports (anchor = report, sentence, short quote) and `Task-*` for the surrounding paragraphs.

Baseline through the operator Hub full profile (`rhenium run`, Linux x86_64 Docker host, 2026-09-24, verifier image `sha256:ea0f0828734d...`): unchanged starter 0/42 (`run-901ae3ef40d74b46`, complete, score 10); reference 42/42 three times with identical case outcomes (`run-5521d56bbb2348ba`, `run-cd3f72e89b784cfb`, `run-d76756ac56174bb8`, score 100). These are not study-Hub records: the study Hub must be re-seeded from the operator database before `rhenium-study e0` can reproduce them, because the verifier images changed on 2026-09-24.

Every overlay patches `addons/sourcemod/scripting/confoglcompmod/CvarSettings.sp`, the only
file the oracle changes. The seven reports are task-authored contracts over the frozen
upstream module, not reverted upstream commits.

## Preserved contracts

None. The unchanged starter raises a SourceMod exception (`Invalid index -1` in
`CVS_CvarDiff_Cmd`) during the only suite boot, and the verifier fails that boot closed,
so all 42 cases are `F` on every starter run. The maintainer's 1.0.0 and 1.2.0 NOP runs
recorded the same fail-closed 0/N. Every case is therefore a `target` by observation.
Without a passing starter baseline there is no preserved set and no compat-negative
control, and joint-compatibility qualification is not available for this task.

## Controls (all executed through `rhenium run`; all behaved as declared)

- `tn-bounded-string-numeric` (target-negative): the oracle whose drift check treats every bounded ConVar as matched by numeric equality (`validation/candidates.py` minus-bounded-string). Observed: `run-8a2f74a3e7e240c6`, 41/42, failing `bounded-string-finite-writeback`.
- `tn-finite-writeback-single-pass` (target-negative): the oracle whose drift correction runs once instead of repeating until the finite callback chain settles (minus-finite-return). Observed: `run-e5b8bfa6cda24aee`, 40/42, failing `bounded-string-finite-writeback`, `finite-cross-callback-return`.
- `alternative-reverse-apply` (alternative): the pack's reference-derived alternative (reverse activation order, `strcmp` comparison). Observed: `run-228dc4b54be54be3`, 42/42, failing none.

## Exclusions / remarks

- Unasserted (excluded) clauses: `Task-preserve-gpl` (pre-case package gate) and
  `Task-no-tests-edit`.
- Admissible for target evidence; not qualified for joint compatibility (no preserved case).
