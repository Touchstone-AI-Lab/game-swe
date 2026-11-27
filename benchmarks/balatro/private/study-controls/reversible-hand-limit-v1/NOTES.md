# reversible-hand-limit-v1 E0 notes

## Controls in the manifest

- `M03-snapshot-restore` (target-negative): `add_to_deck` stores the limit and `remove_from_deck` restores it. Breaks paragraph 3, no reset to a snapshot. A single owner still works, so `solo.*` pass. Fails the nine target cases and no other case.

`alternative-public` is an independent implementation written from the public contract without reading the gold control: a per-instance ledger of what each physical Joker added, so removal gives back exactly that amount. It was reviewed, sealed and passed every required case on the real engine.

## Preserved contracts

- A bought target adds +2 and a sold target removes it (paragraph 2): `solo.buy`, `solo.sell`, `before.buy`.
- Buying a native Juggler adds its own +1 on top of a held target (paragraphs 2 and 4): `background.buy`.

All four stay overlap: `M01-double-add` and `M02-no-remove` fail them along with target cases.

## Frozen controls left out of the manifest

- `M01-double-add`: adds twice the amount. Fails target cases and the preserved `solo.buy`, `solo.sell`, `before.buy`, `background.buy`.
- `M02-no-remove`: `remove_from_deck` does nothing. Fails target cases and the preserved `solo.sell`, `before.buy`, `background.buy`.

## Compatibility-specific negative

This task has no compatibility-specific negative: the manifest has no `compat-negative`.

## Role changes

- `identities`: `preserved` to `runtime-sentinel`. It reads that the five prepared objects were distinct, were all removed and that nothing is owned (`scenario.py:95-97`). Distinctness is fixture data, and `background.sell` already checks the removed list and the owned list. The case proves the scripted lifecycle consumed the declared objects.

## Statements not mapped as clauses

- "A sale need not discard already-held excess cards immediately" is a permission. Both readings pass: `background.sell` does not read the hand count, and `real_play` reaches 8 either way.
- "Storage layout is unrestricted" is a permission. The exclusions in paragraph 4 are scope limits.

## Not determined

- No engine was run. The gap in `rhl-no-reapply-on-incidental-events` comes from reading `scenario.py:73-94`; no reapplying candidate was executed.
