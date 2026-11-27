# growth-v2 / mixed-eights

The behavior contract remains CONTRACT.md's ordinary, no-copy, no-debuff, no-retrigger contract. Each successful blind adds 2 once; every later main Joker scoring phase adds the current growth to Mult. Difficulty: uncalibrated.

This version adds a distinct fixture: six-card hand limit, mixed-suit rank-8 deck, three played hands in round 1, two in rounds 2 and 3, and a third consecutive successful blind. Initial preparation records every modified field and then seals. The Ox boss is selected before play; its money effect does not debuff cards or change scores. The suite checks the actual boss key and plain cards.

Sequence: discard 1; high card / pair / four-of-a-kind (709 total); cash-out/shop; pair / four-of-a-kind (932); cash-out/shop; high card / four-of-a-kind (1077); cash-out/shop. Growth is 0 until the first blind ends, then 2, 4, 6. Each winning hand leaves 2 held cards. Formulae, mutations and acceptance rationale are frozen in CASE-MUTATION-MATRIX.md before implementation.

No score, growth, completed-round count, blind chip target or hand level is assigned by the fixture. Read-only observation is independent of candidate source and names. All contexts originate in the real engine. Field validation/missing cases fail closed. Behavior failures are accumulated; unexecuted dependent checks remain explicit.
