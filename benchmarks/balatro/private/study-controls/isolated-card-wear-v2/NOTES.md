# isolated-card-wear-v2 E0 notes

## Controls in the manifest

- `M01-stale-cache` (target-negative): a per-card cache survives `set_ability`, so reapplication keeps old wear. Breaks bullet 4, exactly two fresh uses. Fails the twelve target cases and no other case.
- `M02-last-reward` (target-negative): the second use pays 0. Breaks bullet 2, full +20 on the second use. Fails `b.last`, `a.last`, `pair.last`, all target.
- `M04-additive-refresh` (target-negative): reapplication sets previous uses plus 2. Breaks bullet 4, does not add old uses. Fails eleven target cases and no other case.

`alternative-public` is an independent implementation written from the public contract without reading the gold control: wear is kept in a weak side table keyed by the physical card, so no center or ability table is shared. It was reviewed, sealed and passed every required case on the real engine.

## Preserved contracts

- Per-card reward and use on a first score (bullets 1 and 3): `pair.first`.
- Holding, discarding, dealing and changing blinds leave uses alone (bullet 1): `r2`, `discard.held`.
- The three applications follow the normal Tarot lifecycle (bullet 4): `applications.lifecycle`.
- Description reads and later frames change nothing (bullets 1 and 5): `stable`.

`pair.first`, `r2` and `discard.held` stay overlap: `M03-shared-prototype` fails them along with target cases.

## Frozen controls left out of the manifest

- `M03-shared-prototype`: reads and writes uses on the shared center config. Fails all twelve target cases and the preserved `pair.first`, `r2`, `discard.held`.

## Compatibility-specific negative

This task has no compatibility-specific negative: the manifest has no `compat-negative`.

## Role changes

None.

## Statements not mapped as clauses

- "Internal state layout is unrestricted" and "equivalent internal designs ... are accepted" are permissions.
- The Scope exclusions in paragraph 2 are limits, not obligations.

## Not determined

- No engine was run. The chip gap in `icw-reapply-no-immediate-reward` comes from reading `scenario.py:33-37,60-63`; no candidate with an immediate chip reward was executed.
