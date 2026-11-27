# Harbor workspace

Complete this task in `/app/addon`; every required file must be written under that directory.

# Hot Object Round Controller

## 1. Background and goals

- **T4-GOAL-01** Implement a server-authoritative three-player Hot Object round system supporting `exploding` and `infectious`, normalizing touches, deaths, respawns, disconnects, the deadline and cleanup into a deterministic state machine.
- **T4-GOAL-02** The plain Lua core is responsible for event ordering and settlement; the adapter provides both a deterministic Dispatch entry point and integration with real GMod `StartTouch/Touch`, Player Hooks and Timers.

## 2. Required files

- **T4-FILE-01** You must submit:

```text
addon.json
lua/rhenium_hot_object_round/controller.lua
lua/rhenium_hot_object_round/server.lua
```

You must not depend on the Workshop, third-party Addons, external packages, network services, or client-authoritative code.

## 3. Core public interface

- **T4-API-01** `lua/rhenium_hot_object_round/controller.lua` returns `Controller` and provides:

```lua
Controller.new(options)
controller:start(event_id, round_id, variant, players, holder_id, deadline)
controller:touch(event_id, object_id, object_revision, player_id, player_revision, sequence, now)
controller:death(event_id, player_id, revision, now)
controller:disconnect(event_id, player_id, revision, now)
controller:respawn(event_id, player_id, old_revision, new_revision, now)
controller:tick(now)
controller:snapshot(now)
controller:save(now)
controller:shutdown()
```

- **T4-API-02** `Controller.new(options)` accepts `object_id`, `object_revision` and an optional `state`; the defaults are `hot:1` and `1` respectively. An invalid object configuration returns `nil,"invalid_options"`; an invalid `schema_version` returns `nil,"invalid_state"`.
- **T4-API-03** Mutating interfaces return `ok:boolean,code:string,data:fresh_table`; snapshot/save return detached tables; shutdown returns `true,"shutdown"` every time.

## 4. Identifiers, time and stable error codes

- **T4-DATA-01** event/round/object/player IDs have length `1..128` and match `^[A-Za-z0-9][A-Za-z0-9_.:-]*$`; revision and sequence are positive integers; now/deadline are non-negative finite numbers.
- **T4-TIME-01** Every call that carries a time uses `effective_now=max(valid_now,last_now)`. Time going backwards must not reopen a round, postpone the deadline, or change an already-settled result.
- **T4-ERR-01** Stably distinguish: `invalid_options`, `invalid_state`, `invalid_event`, `event_conflict`, `invalid_round`, `invalid_players`, `invalid_holder`, `invalid_time`, `round_closed`, `wrong_object`, `invalid_player`, `stale_sequence`, `shutdown`; the adapter additionally has `unbound`, `invalid_kind`.

## 5. State machine and start contract

- **T4-SEM-01** The only state sequence is `waiting → active → resolving → finished → cleanup`. `resolving` is an auditable state within a single settlement; even if the same call has already entered finished by the time it ends, it must be written to the audit.
- **T4-SEM-02** start can succeed only in waiting; it must receive exactly three mutually distinct stable player IDs, one of them as holder, a valid variant, and an absolute deadline strictly later than last_now. The three players start with `revision=1,alive=true,connected=true,infected=false`.
- **T4-SEM-03** start freezes round_id, variant, object logical ID+revision, the three participants and the deadline, and on success returns `true,"started",{holder=...}`.

## 6. Touch, event replay and generation

- **T4-SEM-04** All start/touch/death/disconnect/respawn share an event-ID namespace. A retry with exactly the same method and arguments returns the original result; reusing the same ID for a different event or arguments returns `event_conflict`.
- **T4-SEM-05** When active and `effective_now < deadline`, touch accepts only the exact object ID+revision, a player that is alive+connected and whose revision matches exactly, and an integer sequence strictly greater than the global `last_sequence`.
- **T4-SEM-06** A successful touch changes holder to that player, updates last_sequence, and records `{from,to,sequence}`. infectious additionally marks the player who touched the holder as infected. A wrong generation, dead/disconnected players and old sequences must not transfer.
- **T4-SEM-07** For events produced by the adapter at the same instant, the server assigns strictly increasing sequences in order of receipt; the core accepts only strictly increasing sequences, so the same input event sequence produces the same log; sequences must not be generated from `pairs` table traversal order.

## 7. Death, disconnect and respawn

- **T4-LIFE-01** death marks the player with the matching revision as not alive; disconnect marks them as not connected. If that player is the holder, select the first of the other alive+connected players in lexicographic order of player ID; if there is no candidate, settle immediately with the corresponding reason.
- **T4-LIFE-02** `respawn(event_id,player_id,old_revision,new_revision,now)` accepts only the current old_revision with `new_revision>old_revision`, then sets the new revision, alive=true, connected=true, and returns `true,"respawned",{revision=...}`. Touches with the old revision are permanently invalid.

## 8. Deadline, variants and cleanup boundary

- **T4-TIME-02** When `effective_now >= deadline`, an active round is settled exactly once; the deadline boundary itself is already closed, and touch returns `round_closed`. `settlements` can only go from 0 to 1.
- **T4-SEM-08** The exploding result records `reason`, the current holder, `eliminated={holder}`, winners consisting of the other alive+connected players sorted by ID, variant and settled_at.
- **T4-SEM-09** infectious permanently records the player as infected on each successful touch; the settlement result records the current holder/eliminated entries, and winners contain only the other alive+connected and uninfected players, sorted by stable ID. exploding does not set infection, and winners contain the other alive+connected players. The implementation must not be required to use a specific internal table structure or reference algorithm.
- **T4-TIME-03** finished enters cleanup when `effective_now >= deadline+1`, writes one cleanup audit entry, and must not repeat the consequence or settlement.

## 9. Snapshot and persistence schema

- **T4-PERSIST-01** snapshot exposes at least `schema_version=1,status,round_id,variant,holder,deadline,object_id,object_revision,last_sequence,last_now,settlements,result,audit` and all player states; lists and nested tables are detached and stably sorted.
- **T4-PERSIST-02** save stores, on top of the snapshot, the complete event replay records. After reconstruction, state, result, audit, revisions, sequence, settlements, and exact retries of successes/failures stay consistent, and it will not settle again.
- **T4-PERSIST-03** Saved state must not contain Player, Entity, functions, userdata, Hook or Timer.
- **T4-PERSIST-04** The constructor must fully validate the types, uniqueness and mutual consistency of player ID/revision/alive/connected/infected, event replay records, audit times, status/deadline/result/settlements, holder, sequence and object generation; unknown, missing, duplicate or contradictory state uniformly returns `invalid_state`; checking only `schema_version` is not allowed.

## 10. Server-side adapter and real APIs

- **T4-API-04** `lua/rhenium_hot_object_round/server.lua` returns the adapter and provides:

```lua
adapter.Install(options)
adapter.BindPlayer(player, logical_id, revision)
adapter.BindObject(entity, object_id, revision)
adapter.StartRound(event_id, round_id, variant, players, holder, deadline)
adapter.Dispatch(event)
adapter.Snapshot()
adapter.Save()
adapter.Shutdown()
```

- **T4-NATIVE-01** Install registers named `PlayerDeath`, `PlayerSpawn`, `PlayerDisconnected`, `EntityRemoved` Hooks, plus a single `.05`-second repeating Timer that advances the core tick.
- **T4-NATIVE-02** BindObject stores the logical generation and wraps the entity's existing `StartTouch` and `Touch`: first call the original callback, then pass the real other into the same Dispatch touch path. Both physics callbacks must be able to trigger a transfer.
- **T4-NATIVE-03** PlayerDeath/Disconnected send the corresponding core events; the first PlayerSpawn only marks the player as spawned, and each later one increments the bound revision by one and calls the core respawn.

## 11. Authority boundary and adapter Dispatch

- **T4-TRUST-01** Player, object identity, revision, the default sequence and the current time come only from server bindings/CurTime; unbound objects return `unbound`, and the client cannot impersonate a participant or generation.
- **T4-ADAPTER-01** Dispatch supports at least `kind="touch"`, using optional `event_id/sequence/now` or server-generated values; an unknown kind returns `invalid_kind`. Passing through any test adapter cannot substitute for real physics Touch integration.

## 12. Shutdown, out-of-scope items and prohibitions

- **T4-LIFE-03** Install/Shutdown are idempotent. Shutdown removes all of this Addon's Hooks/Timers, releases bindings and freezes core events; unfinished hot objects/temporary objects created by the Addon must also be cleaned up.
- **T4-SCOPE-01** This task does not cover client HUD, network prediction, damage values, gamemode scoring, or lobbies of more than three players. The core must not access GMod globals, files, the network or the console.
- **T4-SCOPE-02** You must not implement only the deterministic adapter while omitting real `StartTouch/Touch`; no TODOs, empty shells or "not implemented" may be left behind.

## 13. Acceptance criteria

- **T4-ACC-01** Three stable players, both variants, and the full waiting/active/resolving/finished/cleanup state contract can be verified repeatably.
- **T4-ACC-02** touch sequence, event replay, object/player generation, time going backwards and the deadline boundary are all deterministic and replay-proof.
- **T4-ACC-03** The holder's death, disconnect, and the new revision on respawn hand over correctly; each settlement/consequence happens exactly once.
- **T4-ACC-04** The StartTouch/Touch paths with three real Bots and a real physics entity work, and share the same server-side Dispatch authority.
- **T4-ACC-05** save/load across two processes preserves audit/result/dedup; after Shutdown no Hooks, Timers or temporary objects remain.

Suggested completion time: 390 minutes.
