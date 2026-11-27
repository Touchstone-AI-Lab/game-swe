# Common Neighbors — public contract v2

Authored difficulty: **medium**; calibration: **unmeasured / 待校准**. Repair ordinary Common Joker `j_lja2_neighbors`, mod `live_joker_adjacency_v2`, prefix `lja2`, cost $4. This is an authored repair task, not a historical upstream bug.

During each played hand's normal main Joker scoring, **each owned physical instance** independently adds **+3 Mult for each immediately adjacent owned Common Joker** in the current Joker row. Common means normal numeric rarity 1. There can be zero, one or two qualifying neighbors. Another Common Neighbors instance is itself Common and can qualify as a neighbor; it does not copy or recursively calculate anyone's effect. The instance never counts itself, distant objects, a missing neighbor or the opposite end of the row. Contributions from all owned instances add normally.

The row at that hand's scoring is authoritative. Real rearrangement, selling a neighbor or a target, and acquiring another instance change the next hand's contributions. A surviving instance must not inherit another's cached contribution or position. There is no persistent accumulation across hands, and sold objects no longer contribute. Preserve physical identities, the player's chosen order and other Jokers' normal behavior.

Scope: one or more ordinary instances, ordinary Common/Uncommon neighbors, seeded gameplay, legal row rearrangement, ordinary purchase/sale and progression across blinds. Copying, retriggers, debuffs, editions, save restoration and custom rarities are excluded. Neighbor effects remain active and compose normally with this rule. Internal cache layout and the particular equivalent scoring implementation are not prescribed.

Editable files are `main.lua` and `lib/adjacency.lua`; keep the supplied manifest unchanged. Do not modify private fixtures, observers, runtime, dependencies or external files. The provided loadable starter is to be repaired; this contract and source files are sufficient public materials. Private layouts, expected scores and reference implementations are not part of the public package.
