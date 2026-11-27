# seeded-effect-stream-v1 E0 notes

## Controls in the manifest

- `M01-per-card` (target-negative): triggers on `context.discard`, so it pays and draws once per card. Breaks paragraph 2, one reward per operation. Fails the four `.payouts` cases, all target.
- `M02-repeat-first` (target-negative): caches the first reward. Breaks paragraph 3, next draw on each operation. Fails the four `.payouts` cases, all target.
- `M03-score-advances` (target-negative): draws from the correct stream during `joker_main` without paying. Breaks paragraph 2, ordinary scoring must not consume the sequence. Clean scenes pass; fails `noise.payouts` and `isolated`, both target.

`alternative-public` is an independent implementation written from the public contract without reading the gold control: the reward leaves through the returned effect table, with an explicit seed for the dedicated stream. It was reviewed, sealed and passed every required case on the real engine.

## Preserved contracts

- Native discard behavior (paragraph 4): `*.actions`.
- No reward from observation (paragraph 2): `*.stable`.
- Native Lucky scoring and income unaffected, no Chips or Mult added (paragraph 4): `noise.native_noise`.
- Same seed reproduces (paragraph 3): `reproduce`.
- A different seed differs (paragraph 3): `different_seed`.

## Frozen controls left out of the manifest

None. All three frozen mutants are in the manifest.

## Compatibility-specific negative

This task has no compatibility-specific negative: the manifest has no `compat-negative`.

## Role changes

- `clean1.native_noise`, `clean2.native_noise`, `other.native_noise`: `preserved` to `runtime-sentinel`. Without noise the scenario plays no hand, so `keys` and `income` are empty and zero by construction, and `hands` and `chips` only confirm that no hand was played (`scenario.py:52,71-75`). They prove the scene stayed free of noise. `noise.native_noise` stays preserved.

## Statements not mapped as clauses

- "The native API form is ..." and "An equivalent implementation is allowed ..." define the rule and its permission; `ses-stream-key` covers both.
- Paragraph 5 lists scope limits.

## Not determined

- Whether the native Lucky draw paid money in the noise scene. `native-oracle.json` records 7 chips, so Lucky Mult did not fire, but the stored run results hold positional pass or fail only. For that reason `ses-lucky-money-separate` is `weak`.
- No engine was run.
