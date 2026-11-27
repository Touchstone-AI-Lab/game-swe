# H1 v2 private rule / scenario / expected / defect matrix

Specification precedes candidate authoring. Native prerequisite: `validation-charge-prerequisite-v2-dev1.json`, 35/35, three genuine checkpoint restores/four processes. The v3 initialized-load boundary is retained. No blank-MENU load repair or arbitrary checkpoint support is claimed.

| Rule | Scenario | Expected | Defect |
|---|---|---|---|
| Independent state/owners | Core add A, discard A, add B; independent second state | A2/B0, second state empty | Shared owner/state balance |
| Idempotent receipt/history | Core repeated discard/consume, replay after later membership changes, conflicting reuse | Original receipt, no repeated mutation, atomic conflict | Duplicate application; lost history |
| Domain and membership validation | Invalid form/kind, missing/retired owner, invalid event followed by valid same ID | Structured errors without state change | Partial update or ID reservation on failure |
| Read and snapshot isolation | Mutate returned view, receipt, snapshot and restored input | Original state and replay unchanged | Shallow snapshots or aliases |
| Canonical atomic restore | Nonzero and consumed zeros; unsupported version, malformed and illegal mid-history | Exact state/history or unchanged old state | Zero resurrection; failed restore pollution |
| Cap and metamorphic ownership | Interleave owners, saturate at 6, remove one, add a fresh owner; reorder legal independent events | Per-owner balances unchanged by interleaving | Global or row-based accounting |
| Native ordinary play | Fresh process, A created before discard; recruit B after discard | A2/B0, actual operation count +1 | Charge-by-card, reset on acquisition |
| Nonzero restore | Save A2/B0; reorder; discard to A4/B2; save again | IDs/unequal balances/native state retained, full responses | Row reassignment or lost state |
| Consume and zero restore | Actual Pair uses total +6, both zero; save/quit/new process/load | 208 chips, zero stays zero | Display-only restore; consumption history lost |
| Membership after restore | Discard, sell A, recruit C, real High Card | B keeps2, C0, score39 then zero | State transfer, removed-owner resurrection |
| Uninterrupted equivalence | Separate fresh process repeats the same membership/actions without restarts | Same normalized public trajectory and score sequence | Save/load-specific divergence |
| Existing ordinary limits | Additional real discards up to cap then two real hands | Cap6 per active instance, one consumption, next hand zero | Missing cap or repeated score |

Planned correct strategies: directly maintained owner/receipt map plus history; append-only journal with state derived by replay. Same public API and native suite, not renamed copies. Planned base combines detached-snapshot failure and incorrect zero restoration with row-based restored ownership. Single-fault controls: duplicate events; shallow snapshot; zero restore; failed restore pollution; row reassignment; restored display-only scoring. These six controls cover distinct Hard obligations; their count is recorded before implementation rather than forced to a nominal 2–4. Core-only discriminators still execute the complete native suite. No startup crash/RPC timeout is an intended rejection.

Native snapshots are candidate-owned; every restoring process uses the saving candidate's identical bytes. Fixture prepares only the declared start. LOADPREP has zero targets and no preparation calls. Observer reads semantic displays/identities and engine results; no expected-value writeback. Core protocol calls use isolated state, never substitute for real play or native persistence. Wrong semantic results continue when the required actions remain safely observable; infrastructure gaps remain incomplete.
