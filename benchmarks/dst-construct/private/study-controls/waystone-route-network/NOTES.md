# waystone-route-network — authoring notes

## Design rationale

The task combines a graph problem whose answer must be *deterministic* with an exactly-once payment
lifecycle, then forces both through real engine objects.

- **Pure core (`scripts/waystones/network.lua`)**: nodes with a per-owner cap, undirected deduplicated links whose
  integer cost is derived from geometry (`max(1, floor(d + 0.5))`, length gate on squared distance so the
  boundary is exact), cheapest route with a published three-level tie-break (cost, hops, lexicographic
  node-id sequence), and a reserve/commit/abort ticket lifecycle with request-id deduplication, cooldown
  (`now < cooldown_until` rejects), expiry (`now >= expires_at` expires), lazy expiry inside every call,
  commit-time route revalidation (`route_changed`) and full save/load.
- Every formula is written so Lua 5.1 and 5.4 agree: all tested coordinates are integers or `.5` values,
  `cost_per_unit` values are dyadic (0.25), costs/prices are compared numerically only (never through
  `tostring`), ticket ids are opaque strings (only uniqueness is asserted).
- The tie-break cases were designed against the usual wrong implementations: BFS by hops (graph `cheap`),
  Dijkstra with strict `<` relaxation and no hop rule (graph `hops`: the longer-hop path is discovered
  first), first-found / last-found equal labels (graphs `skew`, `late`, `early`, in both directions and both
  insertion orders), predecessor-only tie-breaking and "compute one direction and reverse" (graph `deep`:
  `s->t` must be `s,a,z,t` while `t->s` must be `t,c,b,s`).
- **Component (`waystonenetwork`)**: coordinates only from `entity.Transform:GetWorldPosition()`, identity only
  from `player.userid`, fare from the real `inventory` (`Has` + `ConsumeByName`, refund through
  `SpawnPrefab`/`SetStackSize`/`GiveItem`), movement through `Physics:Teleport` or `Transform:SetPosition`,
  `onremove` listeners per bound entity, rebind-after-load (`rebound = true`), published strict step order
  in `Travel`.
- The rollback obligation is made observable on a synchronous server: the traveler holds exactly `price`
  gold in one stack, so any legitimate charge empties the slot and the base-game inventory pushes
  `itemlose` on the player; the suite's listener removes the intermediate anchor at that moment, so the
  component's own `onremove` hook removes the node and the following `commit` must fail with
  `route_changed`. The suite then checks the refund and the restored position in the real engine.

## API verification against the pinned build (24700372)

Checked in `data/databundles/scripts.zip` from the verifier image (extracted to /tmp, deleted afterwards):
`Inventory:Has(item, amount)` returns `enough, found`; `Inventory:ConsumeByName(item, amount)`;
`Inventory:GiveItem`; `Inventory:RemoveItem` pushes `itemlose` when a whole slot is removed;
`prefabs/goldnugget.lua` has `stackable`; `Physics:Teleport(x, y, z)` is used by `consolecommands.lua` and
`entityscript.lua`; `MakeCharacterPhysics` exists in `standardcomponents.lua`; `EntityScript:ListenForEvent`
/ `RemoveEventCallback` clean `event_listeners[event]` to nil when the last callback goes (this is what the
listener-release assertion reads); `EntityScript:Remove` pushes `onremove` before retiring the entity;
`EntityScript:RemoveComponent` calls `OnRemoveFromEntity`; `AddModRPCHandler` exists in `modutil.lua`.

## What each control shows (all run on the real dedicated server, full profile, after the last suite edit)

| control | result | shows |
| --- | --- | --- |
| reference | 100, complete, passed | the contract is satisfiable |
| alternative | 100, complete, passed | a closure-based core with array/edge-list state and a forward label search carrying whole paths, plus a component where the *world* listens to each entity and a separate wallet/preflight decomposition, passes from exam.md alone; integration regexes are not reference-specific |
| nop | 0, complete=false, not passed | an empty starter cannot pass (no modmain.lua, so the server suite cannot be hosted) |
| rounding-floor | hidden 1, 5 | published rounding rule |
| tiebreak-ignores-hops | hidden 2, 5 | hops tie-break |
| blocked-hop-allowed | hidden 3, 5 | blocked nodes as intermediate hops |
| cooldown-boundary-inclusive | hidden 4, 6 | `now == cooldown_until` is allowed |
| expiry-boundary-exclusive | hidden 4 | `now == expires_at` is expired |
| commit-skips-revalidation | hidden 5, server 3 | route revalidation at commit |
| save-drops-request-history | hidden 6, server 4 | request history persistence |
| cooldown-before-dedupe | hidden 6, server 2, 4 | published reserve step order |
| charge-without-funds-check | server 2 | all-or-nothing fare on the real inventory |
| skips-proximity-check | server 2 | real-position origin check |
| no-onremove-cleanup | server 3 | `onremove` must remove the node |
| no-rollback-on-commit-failure | server 3 | refund + position restore |
| listeners-leak-on-removal | server 4 | `OnRemoveFromEntity` listener release |

Every hidden case and server cases 2–4 are failed by at least one negative; server case 1 is the
attach/authority case (it still asserts the owner cap of 4 and the 60/61 link boundary on real anchors).
All negatives load and run (complete=true).

## Weak / unasserted

- **Regex only**: the RPC handler (no clients on the headless server), the periodic `tick` task and its
  `:Cancel()` (a synchronous suite cannot wait for a timer), which teleport branch ran (both a
  Physics-bearing and a Transform-only traveler are moved and checked, but either API moves both), and the
  `Class`/method definition style.
- The numeric values of `ticket_ttl` and of the 30 s cooldown are not probed on the server (no timers); the
  cooldown is observed only as "second trip rejected / still rejected after load".
- The clock offset restored by `OnLoad` cannot be distinguished from zero inside one process.
- `Network.load` of a *table* with an unrecognized layout is not exercised because the save layout is
  implementation-defined; nil, false and a string are.
- Refund splitting above `stackable.maxsize` (prices over 40) is published but not exercised.
- The listener-release assertion reads the base-game bookkeeping field `entity.event_listeners.onremove`
  (published in exam.md). It accepts both `entity:ListenForEvent("onremove", fn)` and
  `world:ListenForEvent("onremove", fn, entity)`.

## Deviations and things to know

- `pack/runtimes.json` is the real file with `task_bindings` rebound to this single task: the Hub rejects
  bindings for task ids that are not in the catalog, so a byte-identical copy would not load next to a
  one-task catalog. The runtime definition itself is unchanged. `pack/benchmark.json` is a byte copy.
- Server case 4 calls `TheWorld:RemoveComponent("waystonenetwork")` and immediately re-adds the component
  (also on failure), so the world keeps a working component. No world events are pushed and nothing is
  saved; every created entity is removed through a scoped helper even when an assertion fails.
- Server cases share one world component, so each case uses its own node-id prefix (`s1-`…`s4-`), owner and
  traveler userids, and far-apart coordinates.
- Nothing was written to the benchmark repository. Nothing is left unrun: reference, alternative, NOP and
  all 13 negatives were evaluated with `tools/eval.sh`; raw outputs are under `runs/<control>/`.
