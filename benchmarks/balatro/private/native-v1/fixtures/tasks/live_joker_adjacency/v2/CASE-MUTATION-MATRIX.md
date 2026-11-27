# M3 v2 — private rule / scenario / expectation / defect matrix

Frozen before candidate authoring. Ordinary native Credit Card, Splash and Four Fingers keep their real effects. Single Heart-2 hands have 7 base chips and 1 base Mult; a legal five Heart-2 hand is used only to progress the blind. All setup occurs before the first blind; subsequent layout and ownership changes use real RPC gameplay.

| Rule | Scenario | Expected semantic result | Target defects |
|---|---|---|---|
| Ordinary one-instance behavior | Fresh process: Credit, T, Four Fingers; two single-card hands | +3 Mult each hand, 28 chips each, same row and objects | Starter and mutants must retain a complete ordinary success scene |
| Per-instance ownership; T also qualifies as Common | Fresh process: Credit, T1, T2, Four Fingers, Splash | T1 +6, T2 +3; total 70 chips | Shared contribution cache; excluding target-as-neighbor |
| Current position after native rearrangement | T1, Four Fingers, Credit, T2, Splash | T1 +0, T2 +6; 49 chips; same physical IDs in requested order | Cached initial index; shared result; wraparound |
| Selling a neighbor changes surviving effects | Sell Credit, leaving T1, Four Fingers, T2, Splash | Only Credit removed, normal sale income, next hand 28 chips | Stale position and cache pollution |
| New instance comes from real shop purchase | Win blind, cash out; buy T3 with its own physical ID; next blind | Exact cost debit, purchased stock identity owned, prior surviving IDs unchanged | Scope/ownership ambiguity; no fixture reinsertion |
| Three adjacent target instances and left endpoint | Rearrange to T1,T2,T3,Four Fingers,Splash | Contributions +3,+6,+3; 91 chips | Shared per-hand value; excluding targets; endpoint wrap |
| Target sale removes only its own contribution | Sell T2, leaving T1,T3,Four Fingers,Splash | T2 physically removed; next hand 49 chips, no contribution transferred | Stale positions; shared value; incorrect endpoint |
| No repeat accumulation or deferred correction | Stable frame observation after each action and normal subsequent hands | Same native ownership and score after 12 further frames; ready controller | Observer must never repair row or effects |

Controls planned: gold; base with related stale-index and shared-per-hand-contribution faults; M01 shared-result only; M02 stale-index only; M03 excludes another target from Common neighbors; M04 wraps endpoints. All use the full suite. These are distinct faults, not new task slots. A coincidentally correct aggregate in one layout does not justify changing that layout's expected score; other fixed layouts distinguish it. Grading uses real total score and native identity/order, not private state or a prescribed return-table shape.
