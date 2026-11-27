# Reversible Hand Limit — proposed contract v1 (not frozen yet)

Difficulty: uncalibrated. Proposal awaits the versioned capability probe; no candidate exists yet.

An ordinary Joker acquired by a normal shop Buy contributes +2 to the player's hand limit while owned. Ordinary sale removes exactly its own +2. Preserve all other active hand-limit contributions, including those acquired before or after it. More than one ordinary physical instance contributes independently; removing one cannot remove another's contribution. After a sale the next actual refill/deal obeys the remaining limit. A sale need not discard already-held excess cards immediately.

Acquisition/removal must happen exactly once per actual instance lifecycle. Merely displaying the card, scoring a hand, changing rounds, or observing the shop does not reapply the effect. After a normal removal a subsequent legal acquisition and removal must still work. Do not reset the whole limit to a default or to a snapshot taken before other owners changed it.

Target registration is planned as mod reversible_hand_limit, prefix rhl, center j_rhl_spacer. No editions, debuffs, retriggers, Blueprint/copy, special slot rules or save restoration are required. Native ordinary Juggler may be another independent hand-limit contributor. No other scored effects are required of this Joker.

Do not edit runtime/fixture/observer/tests/dependencies or external files. The final public contract will omit private scene arrangements and exact score expectations. Storage layout is unrestricted; evaluation observes native limits, identities, real transactions and actual subsequent hand draws.
