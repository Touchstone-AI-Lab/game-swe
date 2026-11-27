# trade-escrow-exchange — authoring notes

## Design rationale

The task is a two-party, server-authoritative item escrow. The pure core (`scripts/tradeescrow/escrow.lua`) is a
small state machine over five phases (`open`, `settling`, `settled`, `canceled`, `expired`); the world component
(`scripts/components/tradeescrow.lua`) turns a ready trade into a real swap between two base-game `inventory`
components. The difficulty is concentrated in rules that are easy to get almost right:

- **Confirmation pinning.** A confirmation names the counterparty's current revision; ANY accepted offer (even the
  same content under a new revision) voids BOTH confirmations, while an identical replay of the current revision
  must void nothing. The replay check deliberately precedes item validation.
- **A single fixed evaluation order** (invalid_argument → expiry → unknown_trade → not_a_party → phase matrix → own
  rules) published as a 6×5 matrix, so every rejection code has exactly one reading. `invalid_argument` does no
  expiry work, which is observable through `tick`'s "newly expired" list.
- **Exact expiry boundary**: `now >= expires_at`, only in `open`; `settling` never expires; a reopened trade keeps
  its original deadline. Expiry is applied implicitly by every call that takes `now` (including `snapshot`/`save`)
  and an implicitly expired id is never re-reported by `tick`.
- **Persisted two-step settlement** (`begin_settle` → plan → `finish_settle`) so a crash between the two is
  recoverable; recovery never replays a swap of unknown progress, it reopens with confirmations cleared.
- **Real inventories.** Counts may span stacks (40 + 2 of a second stack), whole stacks move as the original
  entity, shortfalls are detected with `inventory:Has`, and a delivery into a full inventory (first item lands in
  the active-item slot, the second is dropped on the ground) must be rolled back to the exact prior counts.

All time enters the core through `now`; hidden-suite times are monotonic non-decreasing per instance and the exam
says so, so an implementation that clamps `now` to a monotonic clock is not penalised.

## What each control shows (all run on the real dedicated server, full profile, no network)

| control | result | shows |
| --- | --- | --- |
| reference | 100, complete, passed | reference satisfies every case and check |
| alternative | 100, complete, passed | a closure/ledger core with a table-driven phase gate and a journalled, stack-by-stack settlement (different save format, different trade-id format, different stack selection via `FindItems`) passes from exam.md alone |
| nop | 0, incomplete, not passed | README-only starter cannot pass (no modmain.lua → server suite not injectable) |
| offer-voids-only-own-confirmation | hidden 2 | "both confirmations" obligation |
| replay-voids-confirmations | hidden 3 | identical replay must be side-effect free |
| rejected-offer-consumes-revision | hidden 1 (+ server 2) | rejected offers consume no revision |
| expiry-boundary-exclusive | hidden 4 | `>=` boundary |
| plan-in-open-order | hidden 5 | plan ordered by giver id, not by open order |
| load-drops-settling-phase | hidden 6 (+ server 4) | `settling` must survive save/load |
| settle-moves-whole-stacks | server 2 | exact counts across stacks |
| settle-trusts-offers | server 3 | holdings verified before moving |
| failed-delivery-not-restored | server 3 | rollback after a failed delivery (proves the engine really dropped/held the items) |
| load-skips-recovery | server 4 | `OnLoad` must recover settling trades |
| rpc-offer-pairs-unvalidated | server 4 | malformed RPC pairs are dropped |
| settle-ignores-invalid-entity | server 4 | `counterparty_unavailable` before `begin_settle` |
| remove-keeps-listener / remove-keeps-expiry-task | server 1 (+ lifecycle regex) | `OnRemoveFromEntity` cleanup, observed through engine bookkeeping |

The negatives hit all six hidden cases and all four server cases. `negatives/*.patch` apply with `patch -p1`
inside a copy of `reference/`; `tools/make_negatives.py` regenerates them from anchored single edits.

## Weak or unasserted obligations (see clause-map.json)

- **Unasserted:** the `open` RPC's lookup of `target_userid` in `AllPlayers` — a headless server has no connected
  players. Only the handler's existence is asserted.
- **Weak:** `Now()` continuity across a server restart (the suite cannot restart the server; a plain `GetTime()`
  clock passes); the `ms_playerleft` callback delegating to `OnPlayerLeft` (the event is never pushed, because
  roughly forty base-game listeners such as `hounded` and `worldoverseer` would receive a fake player — the suite
  calls the published `OnPlayerLeft(player)` method instead); the periodic task actually calling `tick`;
  `OnPlayerLeft` forgetting the entity; the `Class` form of the component.
- `Recover()`'s ascending order of `recovered` is published but only exercised with a single settling trade.
- The "one violation per offer" rule means the precedence between `too_many_prefabs`, `prefab_not_allowed` and
  `invalid_count` is intentionally unspecified and untested.

## Known deviations and risks

- **Scope is above the brief's 300–600 line guideline.** reference/ is 917 physical lines (786 non-comment lines
  by the evaluator's count); alternative/ is 828 (731). The prescribed surface (11 core entry points, a 6×5 phase
  matrix, 10 component methods, four RPCs, rollback, recovery, a restart-safe clock) does not fit in 600 lines
  without dropping published obligations. `minimum_lua_lines` is 260, inside the requested 220–280 band.
- **Server case 1 reads engine bookkeeping** (`TheWorld.event_listeners["ms_playerleft"]`, `TheWorld.pendingtasks`)
  and removes/re-adds the component. Both fields and the procedure are published in exam.md, and the runtime build
  is pinned, but this is a dependency on base-game internals rather than on a documented API. It also means the
  later server cases run against a freshly re-added component.
- **Server case 4 reaches the core through the published `component.escrow` field** to create a `settling` trade
  (the only way to simulate a crash between `begin_settle` and `finish_settle` synchronously). The field name is a
  published contract, which constrains the component's layout slightly.
- The delivery-failure scenario relies on pinned-build `Inventory:GiveItem` behaviour for a non-player entity
  (overflow goes to the active item, the next item is dropped). Implementations that pre-check capacity and ones
  that deliver then roll back both pass; the exam describes both outcomes of `GiveItem`.
- Closed trades are kept forever as tombstones (required by "closed ids are never reusable"); the core therefore
  grows without bound on a long-lived world. This is a property of the specified contract, not of the reference.
- Reference rollback is best effort: if returning items to the giver itself failed (giver inventory filled in the
  same frame, which cannot happen synchronously) the result would still be `delivery_failed`.
- Several runs logged the engine's own `An error occured during world gen we will retry!` (one run reached
  `5 of 5`), with and without mutants. Every run still created the world and emitted the suite marker, so all
  results are complete, but world generation on this image is visibly flaky and unrelated to the mod.

## Not run

- No repository checks from AGENTS.md §9 were run: nothing in `/home/moeleak/Projects/SWE-Game` was modified.
- No real multiplayer session (clients sending the RPCs, real `ms_playerleft`, server restart) was exercised.
- The pack was validated with `DstCatalog.load` and evaluated only through `tools/eval.sh`; it was not registered
  with the Hub or built into a Harbor task image.
