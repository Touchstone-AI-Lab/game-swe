# Durable Charge v2

Repair the supplied multi-file mod. Target difficulty: **Hard, unmeasured**. Preserve its public centers and the core API in `API.md`; internal storage is free. This is an authored repair task, not an upstream historical bug.

`j_dc2_charge` is an ordinary Common Joker. Each **valid player discard operation**, regardless of cards discarded, gives every currently owned physical instance +2 charge, capped at 6. Holding, display queries, ordering, acquisition and selling do not generate charge. A newly acquired instance starts at zero; selling one removes only its own state. Charge belongs to physical identity, never row position.

Each instance contributes its current charge as additive Mult to the next real hand's main Joker scoring. After that instance participates, consume its charge once, including a legitimate zero. Further callbacks for the same operation cannot accumulate or consume again. The next hand has no old bonus. `loc_vars(...).vars[1]` is a pure numeric display of that instance's current balance.

The support Tarot `c_dc2_recruit` is consumed normally on use and creates one fresh charge Joker when ordinary Joker capacity permits. It does not transfer a sold instance's charge. Its capacity behavior is ordinary single-item creation, not a competing-producer reservation problem.

At stable `SELECTING_HAND` checkpoints, native save, normal exit and new-process restoration must preserve physical membership, balances (including zero), and core event history. The supported restore entry is: new process → normally start a separate seeded initialization run → wait until fully ready → one native load with its full success response. Initialization creates no target instances. Restored instances come from the saved game. Continuing equivalent operations with or without that restart must produce the same public balances and real scores.

The public ledger API is independently exercised on isolated states, including duplicate/conflicting events, detached views/snapshots and atomic rejection. These protocol calls are separate from native gameplay; no claim is made that the engine naturally generates every malformed sequence. The live adapter must use that same ledger API for membership, charging, score reads and consumption, and persist its snapshot. It must not keep a separate display-only balance or reset restored state during load.

Scope: seeded ordinary play, no copying, disabled/debuffed targets, retriggering, editions, mid-resolution saves, crash recovery, cross-mod event producers, arbitrary capacity modifiers or untrusted-code sandboxing. Both saved and restored processes use the same submission bytes. Preserve normal game callbacks, arguments, returns and exceptions; do not modify fixed components or invoke future callbacks manually. Do not reset unrelated objects or game state.
