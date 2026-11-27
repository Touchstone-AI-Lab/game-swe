# growth-v2 E0 notes

## Controls in the manifest

- `M06-cap-four` (target-negative): correct trigger, growth capped with `math.min(4, ...)`. Breaks bullet 5, "there is no growth cap". Fails `r3.end` and `r3.shop`, both target.
- `M08-four-kind-only` (target-negative): correct trigger, Mult applied only when the hand is Four of a Kind. Breaks bullet 4, every main scoring phase. Fails `r2.pair`, `r2.end`, `r3.high`, `r3.end`, all target.
- `alternative` (alternative): replaces the `main_eval` guard with `not individual and not repetition` plus a per-round `last_awarded_round` marker. A structurally different repair using only public behavior. Fails no case.

## Preserved contracts

- Discards add no growth (bullet 3): `discard`.
- Ordinary hands add no growth (bullet 3): `r1.high`, `r1.pair`. Both stay overlap because `M03-per-hand` fails them. With growth at 0 they say nothing about additive Mult.

## Frozen controls left out of the manifest

- `M03-per-hand`: moves the increment to `context.after`, so growth rises on every hand. Fails target cases and the preserved `r1.high` and `r1.pair`.

## Compatibility-specific negative

This task has no compatibility-specific negative: the manifest has no `compat-negative`.

## Role changes

- `r1.context`, `r2.context`, `r3.context`: `preserved` to `runtime-sentinel`. `end_context` (`scenario.py:32-34`) counts the engine's main end-of-round callback and the engine's held-card count. The observer records them around the candidate (`observer.lua:13-19`), so no reading depends on what the candidate did with the callback. The starter and every frozen control pass. The cases prove the fixture reached the declared two-held-card path.

## Statements not mapped as clauses

- Paragraph 3 "Verification uses actual ..." and "Initialization can prepare ..." describe the evaluator.
- Paragraph 2 exclusions and "No save-restoration behavior is required" are scope limits, not obligations.

## Not determined

- No engine was run. Whether an increment deferred through the event queue is visible at `ROUND_EVAL` is unknown: `scenario.py:27-28` observes right after the state change, with no settling step. If it is not visible, `r*.end` would reject a form the contract does not forbid. This is unverified, so it is not listed as a known issue.
