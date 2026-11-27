---
difficulty: hard
estimated_minutes: 360
domains:
  - voting
  - server-authority
  - timers
  - replication
---

# Server-authoritative world rule ballot

## Background and goal

The server lets online players hold a time-limited vote on preconfigured rules. The proposal, the choices, the electorate, the deadline and the quorum are all determined by the server; a client can only express its own choice. Changed votes, late packets, repeated settlement, players joining midway and world reloads must not change the established contract.

Implement a plain Lua ballot state machine, a server-side world component and a read-only replica.

## Required deliverables

```text
modinfo.lua
modmain.lua
scripts/ruleballot/ballot.lua
scripts/components/ruleballot.lua
scripts/components/ruleballot_replica.lua
```

The pure module exports:

```lua
Ballot.new(options)
Ballot.load(data, options)

ballot:open(proposal, electorate, now)
ballot:cast(voter_id, proposal_id, choice_id, revision, now)
ballot:close(proposal_id, now)
ballot:cancel(proposal_id, now)
ballot:snapshot(now)
ballot:save(now)
```

`proposal` contains at least a unique `id`, two or more unique `choices`, a finite `deadline` and a server-configured `quorum`.

## Core semantics

1. `open` freezes the de-duplicated electorate. Players who join afterwards cannot vote, and original electors who leave still count toward the quorum base.
2. Votes from frozen electors for choices on the choice whitelist can be accepted only before the deadline. `revision` is a strictly increasing non-negative integer per elector.
3. Duplicate and old revisions have no side effects; abstention, if it is allowed, must be an explicit whitelisted choice.
4. `close` is idempotent, and only the latest vote of each elector is counted. When the number of participants does not reach quorum the result is `no_quorum`; when the highest count is tied the result is `tie` and no rule is applied.
5. Counts are output in lexicographic order of option ID. The result of a close at any time after the deadline must be identical to the result at the deadline instant.
6. `cancel` produces a final state that cannot be reopened and applies no rule; a closed or canceled proposal ID can never be reused.
7. `snapshot` exposes only aggregate counts, does not leak individual choices, and returns a new table. `save/load` preserve the electorate, the revisions, the deadline and the final result.

## Return values and data shapes

Hidden tests rely only on the following public shapes:

- `open` and `cast` return a table containing a boolean `ok`.
- `close` and `cancel` return a new table containing `status`, whose value is `"passed"`, `"no_quorum"`, `"tie"` or `"canceled"`; when `status = "passed"`, `choice_id` is the winning choice. Calling `close` on a canceled proposal returns `status = "canceled"`.
- `close` also settles immediately on the current vote counts when `now < deadline` (only server code can call it); a settlement at any time after the deadline gives the same result as at the deadline instant.
- The top level of `snapshot(now)` contains an array `counts`, in lexicographic order of `choice_id`, where each row is `{ choice_id = ..., count = ... }`; a `votes` or `electorate` field must not appear.
- The world component's `Open` and `Cast` return a table containing `ok`, and `Close` returns a result of the same shape as the core `close`.

## DST integration

- Attach `ruleballot` only on the master simulation. The whitelist constrains the RPC entry point and the rules that are actually applied; `Open` can only be called by server code and must accept any proposal with valid fields that the server passes in (including an `id` outside the whitelist, in which case no rule is applied after settlement).
- The component uses `GetTime()` as its clock: `proposal.deadline` is on the same time base; `Close(proposal_id)` settles immediately when it is called by server code, and timer expiry goes through the same path.
- The RPC receives only the proposal ID, the choice ID and the revision; identity comes from `player.userid`.
- The server builds the frozen electorate from the players currently online and schedules settlement with `DoTaskInTime`.
- Apply the mod's own whitelisted rule only when the result is `passed` and there is no tie; client-supplied Lua, commands or arbitrary configuration keys must not be executed.
- Announce the final result with `TheNet:Announce`, and publish a compact aggregate state through net variables and the replica.
- `OnSave/OnLoad` restore in-progress ballots and reschedule the remaining timers; tasks are canceled when the component is removed.

## Base-game API contract

The server RPC, the timer, the announcement and the net variable may be used with the following base-game signatures:

```lua
AddModRPCHandler("rhenium_ballot", "cast", function(player, proposal_id, choice_id, revision)
    local voter_id = player ~= nil and player.userid or nil
end)

local close_task = inst:DoTaskInTime(delay, function()
    component:Close(proposal_id)
end)
if close_task ~= nil then
    close_task:Cancel()
end

TheNet:Announce(message)
inst._ballot_state = net_string(inst.GUID, "ruleballot.state", "ruleballotdirty")
inst._ballot_state:set(encoded_public_state)
```

Net variables should be created before `if not TheWorld.ismastersim then return inst end`; the client reads `netvar:value()` in the dirty event. Do not JSON-encode the save table that contains individual votes directly into a netvar.

The world component must expose `Open(proposal, player_entities)`, `Cast(player, proposal_id, choice_id, revision)` and `Close(proposal_id)`. `player_entities` is converted to `userid` values and frozen only on the server, and the RPC is not allowed to call `Open`.

## Acceptance

- Non-electors, forged choices, old revisions and late votes are invalid.
- Quorum, ties and counting order are fully deterministic.
- close/cancel remain idempotent across retries and reloads.
- A client cannot decide the electorate, the deadline, the quorum or the rule to execute.
- The headless dedicated server tests, on a real server, open a proposal with entities that carry a `userid`, cast votes as players, have the server settle early and assert the result, and perform an `OnSave/OnLoad` round trip; the timer, net state and announcement paths are covered by static integration checks.
- Static checks require that every submitted Lua file is non-empty, that non-comment code totals at least 240 lines, and that the base-game API wiring listed in this document is present.

Use only base-game APIs and assets; copying individual votes to clients is forbidden.
