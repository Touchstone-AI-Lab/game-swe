---
difficulty: hard
estimated_minutes: 360
domains:
  - voting
  - server-authority
  - timers
  - announcements
---

# Server-authoritative World Rule Ballot

## Background and goals

The server lets online players hold time-limited votes on preconfigured rules. Proposals, choices, voters, deadlines and quorum are all determined by the server side; a client can only express its own choice. Vote changes, late packets, repeated settlement, players joining midway and server restarts must not change the established contract.

Implement a plain-Lua ballot state machine, a dedicated-server service module, and a UE4SS entry script.

## Required files

```text
Info.json
scripts/main.lua
scripts/ruleballot/ballot.lua
scripts/services/rule_ballot_service.lua
```

The plain module exports:

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

1. `open` freezes the deduplicated electorate. Players who join afterwards cannot vote; original voters who leave still count toward the quorum base.
2. Votes may be accepted only before the deadline, only from frozen voters, and only for choices on the whitelist. `revision` is a non-negative integer that is strictly increasing per voter.
3. Duplicate and stale revisions have no side effects; abstention, if allowed, must be an explicit whitelisted choice.
4. `close` is idempotent and counts only the latest vote of each voter. When the number of participants does not reach quorum the result is `no_quorum`; when the top vote count is tied the result is `tie` and no rule is applied.
5. Counts are output in lexicographic order of option ID. The result of a close at any moment after the deadline must be identical to the result at the instant of the deadline.
6. `cancel` produces a final state that cannot be reopened and applies no rule; a proposal ID that has been closed or canceled can never be reused.
7. `snapshot` exposes only aggregate counts, does not leak individual choices, and returns a new table. `save/load` preserves the electorate, revisions, deadline and final result.
8. The core module must run in an ordinary Lua environment without any UE4SS global objects.

## UE4SS integration

- Mount the service module only in the dedicated server process; proposals come from a fixed server-side whitelist.
- The service module exposes `Open(proposal, controllers)`, `Cast(controller, proposal_id, choice_id, revision)`, `Close(proposal_id)`, `Save()` and `Load(data)`.
- The console command accepts only the proposal ID, choice ID and revision; identity is derived by the server side from the controller.
- The server side builds the frozen electorate from the currently online controllers and schedules settlement with a delayed task; after `Load` it must reschedule according to the remaining time.
- Apply the mod's own whitelisted rules only on `passed` with no tie; never execute client-supplied Lua, commands or arbitrary config keys.
- Announce the final aggregate result through the output device and the server log; never echo any individual vote.

## UE4SS API usage contract

```lua
local UEHelpers = require("UEHelpers")

-- UE4SS starts Lua mods before the dedicated server owns a valid UWorld, so the
-- authority check and every registration must wait for the world to appear.
-- Palworld's shipping build does not export UGameplayStatics::IsDedicatedServer;
-- UKismetSystemLibrary::IsDedicatedServer is the reflected entry point.
local function MountWhenReady(mount)
    local world = UEHelpers.GetWorld()
    if world == nil or not world:IsValid() then
        ExecuteWithDelay(1000, function()
            ExecuteInGameThread(function() MountWhenReady(mount) end)
        end)
        return
    end
    if not UEHelpers.GetKismetSystemLibrary():IsDedicatedServer(world) then
        return
    end
    mount()
end

local pre, post = RegisterHook(
    "/Script/Engine.PlayerController:ServerAcknowledgePossession",
    function(Context) service:Attach(Context:get()) end)

RegisterConsoleCommandGlobalHandler("rhenium_ballot", function(Cmd, CommandParts, Ar)
    ExecuteInGameThread(function()
        local result = service:Cast(
            service:CurrentController(), CommandParts[1], CommandParts[2], tonumber(CommandParts[3]))
        Ar:Log(result.code)
    end)
    return true
end)

ExecuteWithDelay(remaining_milliseconds, function()
    ExecuteInGameThread(function()
        local result = service:Close(proposal_id)
        print("[rhenium_ballot] " .. result.status)
    end)
end)

UnregisterHook("/Script/Engine.PlayerController:ServerAcknowledgePossession", pre, post)
```

`print` does not support formatting; when formatting is needed, use `string.format` first. `Ar:Log(message)` replies only to the output device that issued the command.

`Info.json` must declare the package name and one install rule with `"Type": "Lua"` and `"IsServer": true`.

## Dedicated-server service contract

After confirming that it is running on a dedicated server, `scripts/main.lua` must publish the mounted service instance as the single global `RheniumService`, and must not pollute any other global name. The service instance supplies its own timestamps; callers do not pass `now`.

```lua
RheniumService:Attach(controller)                                 -- Register a validated controller
RheniumService:VoterIdOf(controller)                              -- Server-derived voter ID
RheniumService:CurrentController()                                -- Issuer of the current console command
RheniumService:Open(proposal, electorate)                         -- electorate may be a list of controllers or a list of voter IDs
                                                                  -- proposal uses a relative deadline_seconds; the server side converts it to an absolute deadline
RheniumService:Cast(controller, proposal_id, choice_id, revision) -- Derive identity first, then forward
RheniumService:CastAs(voter_id, proposal_id, choice_id, revision) -- Server-internal entry point once identity is determined
RheniumService:Close(proposal_id)                                 -- Returns the result table of ballot:close
RheniumService:Save()                                             -- Plain data table
RheniumService:Load(data)
```

## Return conventions

Every method that can fail returns a table: `{ ok = true, ... }` on success, `{ ok = false, code = "<stable error code>" }` on failure. Query methods return data tables directly. The fields this task must implement are listed below.

```lua
ballot:open(proposal, electorate, now) -- { ok = true, proposal_id = id } | { ok = false, code = "invalid_proposal" | "reused_id" }
ballot:cast(voter_id, proposal_id, choice_id, revision, now)
-- { ok = true, revision = n }
-- { ok = false, code = "not_a_voter" | "unknown_choice" | "stale_revision" | "closed" | "past_deadline" }
ballot:close(proposal_id, now)
-- { status = "passed" | "failed" | "tie" | "no_quorum" | "canceled", choice_id = string | nil,
--   counts = { { choice_id = "...", count = n }, ... } in lexicographic order of choice_id }
ballot:cancel(proposal_id, now) -- { status = "canceled" }
ballot:snapshot(now) -- { proposal_id = id, status = "...", counts = { { choice_id = "...", count = n }, ... } }
ballot:save(now) -- Plain data table
```

`snapshot` must not contain the `votes` or `electorate` keys.

## Acceptance

- Non-voters, forged choices, stale revisions and late votes have no effect.
- Quorum, ties and count order are fully deterministic.
- close/cancel stay idempotent across retries and reloads.
- The client cannot decide the voters, deadline, quorum or the rule to be applied.
- The core module contains no UE4SS global objects.
- Headless dedicated-server tests verify service mounting, server-side identity derivation, settlement, and save/load.

Only documented UE4SS APIs and the official Palworld packaging format may be used; replicating individual votes to clients is forbidden.
