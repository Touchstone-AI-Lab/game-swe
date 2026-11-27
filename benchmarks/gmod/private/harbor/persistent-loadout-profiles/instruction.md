# Harbor workspace

Complete this task in `/app/addon`; every required file must be written under that directory.

# Persistent Loadout Profiles

## 1. Background and goals

- **T3-GOAL-01** Implement a server-authoritative system of named Loadout profiles: save weapon and ammo plans, select a preferred profile, and restore after death, respawn, disconnect-and-rebind, and separate server process restart.
- **T3-GOAL-02** Profile normalization, revisions, replay and persistence belong to the plain Lua 5.1 core; real Player and Hook belong only to the server-side adapter.

## 2. Required files

- **T3-FILE-01** You must submit:

```text
addon.json
lua/rhenium_loadout_profiles/profiles.lua
lua/rhenium_loadout_profiles/server.lua
```

`addon.json` must be valid; you must not depend on the Workshop, third-party Addons, external packages, the network, or client code.

## 3. Core public interface

- **T3-API-01** `lua/rhenium_loadout_profiles/profiles.lua` returns `Profiles` and provides:

```lua
Profiles.new(options)
profiles:put(request_id, player_id, profile_name, spec, revision)
profiles:select(request_id, player_id, profile_name, revision)
profiles:get(player_id, profile_name)
profiles:preferred(player_id)
profiles:plan(player_id)
profiles:disconnect(player_id, now)
profiles:save(now)
profiles:shutdown()
```

- **T3-API-02** `Profiles.new({state=optional_state})` returns an instance on success; an invalid saved state returns `nil, "invalid_state"`.
- **T3-API-03** `put`, `select`, `disconnect` return `ok:boolean, code:string, data:fresh_table`; `get`, `plan` return a detached table or `nil,error_code`; `preferred` returns a string or nil; `shutdown` returns `true,"shutdown"` every time.

## 4. Identifiers, profile schema and fixed allowlist

- **T3-DATA-01** For put/select, request/player IDs have length `1..128` and match `^[A-Za-z0-9][A-Za-z0-9_.:-]*$`; profile names have length `1..32` and match `^[A-Za-z0-9_-]+$`; revision is a positive integer. The player ID for disconnect/save comes from the trusted adapter; now advances the clock only if it is a non-negative finite number greater than last_now; any other now does not raise an error and does not lower or change last_now.
- **T3-DATA-02** spec has the form `{weapons={...}}`, containing `1..4` mutually distinct weapon rows. A row is `{class=..., primary=optional_ammo, secondary=optional_ammo}`; ammo is `{type=...,amount=non-negative integer}`; primary and secondary must each be kept separately.
- **T3-DATA-03** The weapon allowlist is a closed set: `weapon_crowbar`, `weapon_pistol`, `weapon_smg1`, `weapon_shotgun`. Anything else returns `invalid_weapon`.
- **T3-DATA-04** The ammo allowlist and post-merge caps are a closed mapping: `Pistol=200`, `SMG1=120`, `Buckshot=32`. An unknown type or invalid amount returns `invalid_ammo`; exceeding the cap after aggregating by type returns `ammo_cap_exceeded`.

## 5. Normalization, ordering and quota

- **T3-SEM-01** Each player has at most 5 distinct profiles; creating a 6th returns `profile_limit`. Replacing an existing name does not increase the count, but the revision must be greater.
- **T3-SEM-02** The `weapons` of the normalized plan are sorted lexicographically by class; all primary/secondary amounts are summed per ammo type, producing a single `ammo` row per type, sorted lexicographically by type.
- **T3-SEM-03** `get` returns `{revision,plan}`; `plan` returns the plan of the preferred profile. All tables are detached from internal state; callers modifying return values must not affect later results.

## 6. Revision, replay and error contract

- **T3-SEM-04** `put` and `select` share a global request-ID namespace. An exact retry with the same method and same arguments returns the original result and does not modify again; a change of method or arguments under the same ID returns `request_conflict`.
- **T3-SEM-05** Each profile's revision increases monotonically; preferred selection has a separate per-player monotonic revision. An equal or smaller revision returns `stale_revision`.
- **T3-ERR-01** Must stably distinguish: `invalid_state`, `invalid_request_id`, `request_conflict`, `invalid_profile`, `invalid_weapon`, `invalid_ammo`, `ammo_cap_exceeded`, `profile_limit`, `stale_revision`, `not_found`, `shutdown`.
- **T3-SEM-06** Invalid input fails before any business state changes. When `request_id` itself is invalid, return `invalid_request_id` and do not record it; as long as the request ID is valid, all put/select successes, business failures and argument failures must be saved, an exact retry returns the same result, and changing any argument returns `request_conflict`.

## 7. Time, disconnect and persistence

- **T3-PERSIST-01** `disconnect(player_id,now)` does not delete profiles or the preferred choice, and returns `true,"retained",{player_id=...}`. `last_now=max(last_now,valid_now)`; time going backwards does not lower the saved clock.
- **T3-PERSIST-02** `save(now)` returns `schema_version=1`, `last_now`, all profiles/choices, revisions and request results; after reconstruction, preferred, plans, failure/success replay and ordering are exactly identical.
- **T3-PERSIST-03** Saved state must not contain Player, Weapon, functions, userdata or process-local objects. The constructor must validate fields, types, uniqueness, allowlist/cap, revisions, preferred references, request shape/result and `last_now` of all player/profile/choice/request rows; unknown, missing, duplicate or mutually contradictory state uniformly returns `invalid_state`; checking only `schema_version` is not allowed.

## 8. Server-side adapter public interface

- **T3-API-04** `lua/rhenium_loadout_profiles/server.lua` returns the adapter and provides:

```lua
adapter.Install(options)
adapter.BindPlayer(player, logical_id)
adapter.HandlePut(player, request_id, name, spec, revision)
adapter.HandleSelect(player, request_id, name, revision)
adapter.Apply(player)
adapter.Save()
adapter.Shutdown()
```

- **T3-ADAPTER-01** Unbound/invalid players return `unbound`. HandlePut/HandleSelect must ignore any identity in the payload and use only the server-side logical ID corresponding to the Player object.
- **T3-ADAPTER-02** `Apply` returns `true,"applied",{weapons=fresh_list,ammo=fresh_list}` on success; stable failure codes include `unbound`, the core's `not_found`, `strip_failed`, `give_failed`, `ammo_failed`.

## 9. Apply order and failure semantics

- **T3-NATIVE-01** Apply first calls `Player:StripWeapons()`.
- **T3-NATIVE-03** After Strip succeeds, call `Player:RemoveAllAmmo()`, ensuring picked-up ammo does not accumulate.
- **T3-NATIVE-04** Call `Player:Give(class,true)` one by one in normalized order, then `Player:GiveAmmo(amount,type,true)` one by one in normalized order; the `true` in `Give` prevents the weapon's default ammo from polluting the normalized plan.
- **T3-NATIVE-05** After everything is granted successfully, call `Player:SelectWeapon(first_successful_class)`.
- **T3-ROLLBACK-01** Strip/RemoveAllAmmo throwing returns `strip_failed`. If any Give throws or returns an invalid Weapon, immediately return `give_failed` and report the previously successful classes in data.given; no ammo may be granted afterwards. GiveAmmo throwing immediately returns `ammo_failed`. The task does not require restoring the pre-Apply inventory, but requires that later stages do not continue after a failure.
- **T3-SEM-07** Repeated Apply must first clear weapons and all ammo, so world pickups and old ammo must not add on top of the normalized plan.

## 10. Hooks and respawn flow

- **T3-NATIVE-02** `Install` registers only named `PlayerSpawn` and `PlayerDisconnected` Hooks that have actual behavior; it must not register empty `PlayerInitialSpawn`/`PlayerDeath` Hooks or empty repeating Timers. `PlayerSpawn` calls Apply at the next scheduling point for a Player that is still valid and bound; `Player:Spawn()` after a real `Player:Kill()` is restored through this path. PlayerDisconnected unbinds the object and calls the core disconnect, but retains the persistent profiles of the logical ID; after a new Player binds the same ID, they can be restored.

## 11. Trust boundary and lifecycle

- **T3-TRUST-01** The logical player ID, allowlist, cap, profile revision and preferred revision are all interpreted by the server side. The client must not specify the Player object, expand the allowlist/cap, or bypass BindPlayer.
- **T3-LIFE-01** `Install` and `Shutdown` are idempotent. Shutdown removes this Addon's two Hooks, clears object bindings, and calls the core shutdown; afterwards put/select return `shutdown` and no longer modify state.

## 12. Plain Lua, out-of-scope items and prohibitions

- **T3-SCOPE-01** The core must not reference Player, Weapon, hook, timer, CurTime, IsValid, files, the network or the console. Only Lua 5.1 standard table/string/number operations may be used.
- **T3-SCOPE-02** This task does not cover client Loadout UI, arbitrary Sandbox/Workshop weapons, weapon attachments, armor, entity positions, or transactional rollback of the pre-Apply inventory. No TODOs, empty shells or "not implemented" errors may be left behind.

## 13. Acceptance criteria

- **T3-ACC-01** Multiple profiles, preferred, the 5/4 limits, the closed allowlist and the 200/120/32 aggregate caps all work per the public contract.
- **T3-ACC-02** primary/secondary are kept, shared ammo is merged and granted only once, weapon and ammo ordering is deterministic, and outputs are detached.
- **T3-ACC-03** Exact retry, conflicts, the two revision sets, disconnect retention, and save/load across two processes have consistent semantics.
- **T3-ACC-04** Strip/Give/GiveAmmo/SelectWeapon on a real Bot, real Kill/Spawn, and PlayerSpawn restoration work; partial Give failure is verified only in deterministic integration and does not enter the ammo stage.
- **T3-ACC-05** Respawn first removes picked-up ammo and then restores the normalized values; after Shutdown no Hooks remain and write operations are frozen.

Suggested completion time: 360 minutes.
