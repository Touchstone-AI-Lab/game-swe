# live-joker-adjacency-v2 E0 notes

## Controls in the manifest

- `M03-exclude-target` (target-negative): the neighbor test also rejects `j_lja2_neighbors`. Breaks paragraph 2, another instance can qualify as a neighbor. Fails `multi.first_score`, `multi.three_score`, `multi.last_score`, all target.

`alternative-public` is an independent implementation written from the public contract without reading the gold control: the whole row is tallied once per hand and each physical instance looks its count up by identity. It was reviewed, sealed and passed every required case on the real engine.

## Preserved contracts

- One instance scores +3 per adjacent Common and does not accumulate (paragraphs 2 and 3): `single.first_score`, `single.repeat_score`.
- Physical identities and the chosen order survive rearrangement, sale, purchase and blinds (paragraph 3): `multi.reorder`, `multi.neighbor_sale`, `multi.shop`, `multi.purchase`, `multi.next_blind`, `multi.three_order`, `multi.target_sale`.
- No change over later frames (paragraph 3): `single.stable`, `multi.stable`.
- `multi.reordered_score` is preserved by evidence only; see the known issue.

## Frozen controls left out of the manifest

Each one fails target cases and exactly one preserved case, `multi.reordered_score`:

- `M01-shared-result`: one count shared by all instances in a hand.
- `M02-stale-index`: each instance keeps its first row index.
- `M04-wrap`: neighbor positions wrap around the row ends.

## Compatibility-specific negative

This task has no compatibility-specific negative: the manifest has no `compat-negative`.

## Role changes

None. `multi.reordered_score` stays `preserved` with overlap, because only a change to `setup` or `runtime-sentinel` is permitted and the case does not merely prove that the fixture ran.

## Statements not mapped as clauses

- Paragraph 4 exclusions and "Internal cache layout ... not prescribed" are scope limits and a permission.
- "The provided loadable starter is to be repaired" and the package statements in paragraph 5 describe the delivery.

## Not determined

- No engine was run. The coincidence in `multi.reordered_score` comes from tracing the starter source, and it agrees with the recorded case table.
