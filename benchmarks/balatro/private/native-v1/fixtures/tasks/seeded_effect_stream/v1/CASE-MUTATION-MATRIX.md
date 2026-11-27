# Private stream rules, scenarios and controls v1

Freeze before candidates. Four fresh processes per whole suite: clean STREAM01 twice, STREAM01 with a real held native Lucky 2 hand after the first discard, and clean STREAM02. Each scene uses real discard cardinalities [1,2,3,1], preserving the held Lucky card until needed. No direct calculate, RNG-state write, later fixture or observer reward. All 27 required cases must run for a complete verdict.

| Rule | Scene | Expected | Defect detected |
|---|---|---|---|
| Ordinary legal actions | All four real discards in each scene | Complete response, one discard counter increment per operation, selected physical cards in discard, no altered Joker identity | Broken action/callback scope, collateral changes |
| Public seeded payout | All scenes; native reference captured before candidates | Actual per-operation dollars match native-oracle.json mapping | Base uses the native lucky_money namespace |
| One payout per operation | One-, two- and three-card discards | Exactly one next reward each, independent of selected count | M01 rewards per-card contexts, advancing/paying several times |
| Advance between operations | Four discards, including nonconstant native sequences | Successive mapped rewards, not a cached first value | M02 reuses first reward |
| Isolation from real native effect | Same seed and trigger sequence, with one Lucky scoring hand between first and second | Unchanged target cash sequence, real native draw keys, positive native score and only native cash during hand | Base stream collision; M03 consumes private stream on unrelated joker_main |
| Repeatability and seed binding | Two same-seed clean processes and other seed | Same-seed target sequences equal; other seed matches its own native reference | Ambient/fixed/randomly reset sequence |
| No observation reward | Read-only bounded frame progression between operations | Stable dollars, no manual callback execution | Poll/display-driven payout |
| Preparation is sealed | All post-initial states | Stage2, same ordinary owned Joker, no observation overflow | Fixture contamination, incomplete telemetry |

Controls: gold follows the public behavior; base changes only the stream key to lucky_money. M01 switches reward trigger to per-card discard. M02 caches first draw instead of advancing. M03 additionally consumes the correct stream once during genuine main scoring, without paying. Three mutants are selected for different cardinality, advancement and trigger-isolation defects; no syntax/transport fault counts as a negative. Role labels are operator metadata and never scoring inputs. Surviving variants remain evidence and cannot be forced to fail by an ad hoc assertion.

Expected complete negative failures: base and M01/M02 fail each scene's payout vector while normal operation cases pass; base additionally breaks cross-scene isolation. M02 violates the advance property; M03 preserves clean scenes but fails noise payouts and isolation. Exact must-pass/must-fail gates will follow these frozen rules and be bound before trial. Infrastructure exceptions, missing responses and missing cases are incomplete.
