# Left 4 Dead 2: Left4DHooks public API regressions

You are working on the GPL-3.0-licensed **Left4DHooks** SourceMod library at
`/app/left4dhooks`. It is a large native bridge used by L4D/L4D2 server plugins.
Consumers reported twelve regressions in public APIs and forwards.

## Reports

> **[#LH-204] `Ammo_t.GetName`.** For every valid entry returned by
> `AmmoDef.GetAmmoOfIndex`, `Ammo_t.GetName` must return that ammo definition's
> stable, non-empty engine name. Passing the result back to `AmmoDef.Index(name)`
> must recover the same index, and repeated reads must agree. Other `Ammo_t`
> behavior must remain unchanged: in particular, reading the name must not change
> `nDamageType`, and the exposed AmmoDef index range must remain valid.

> **[#LH-219] bile-jar projectile forwards.** Creating a real vomit-jar projectile
> must dispatch the documented `L4D2_VomitJarProjectile_Pre` and
> `L4D2_VomitJarProjectile_Post` forwards once for that creation, with the existing
> owner, origin, angles and velocity semantics. The creation detour must not route
> those callbacks through the Molotov forward family. Preserve the documented
> pre-forward blocking/change result and the post-handled return override, as well
> as normal Molotov projectile behavior.

> **[#LH-237] direct infected spawn time.** `L4D2Direct_GetSpawnTimer(client)` is a
> direct accessor for the client's `CTerrorPlayer::m_flBecomeGhostAt` float. It must
> return that stored absolute engine-time value as a `float`, not a
> `CountdownTimer` reference and not a remaining-duration value. Invalid client
> indices return `-1.0`. Keep `L4D_GetPlayerSpawnTime` as the separate relative-time
> API, and do not modify adjacent player state. The public include
> declaration and documentation must match the runtime native.

> **[#LH-246] float weapon attributes.** `L4D2_GetFloatWeaponAttribute` and
> `L4D2_SetFloatWeaponAttribute` must preserve normal decimal-valued weapon
> attributes. `L4D2FWA_PenetrationNumLayers` is the exception exposed through
> this float API: setting it to `3.75` must store the engine's integral layer
> count and read back `3.0`, without changing the adjacent penetration-power
> attribute. Looking up a float attribute for a nonexistent weapon must return
> the documented numeric sentinel `-1.0`.

> **[#LH-251] animation-hook client lifecycle.** A single consumer may install
> the same pre/post animation callbacks for two survivor clients. Disabling and
> then re-enabling the callbacks for one client must leave exactly one callback
> registration for that client, while the peer client's hook remains active.
> A final disable must stop callbacks for only the selected client. Repeated
> enable/disable cycles must not multiply callback delivery.

> **[#LH-258] pipe-bomb forward isolation.** A plugin that subscribes to the
> pipe-bomb projectile creation and detonation forward families, but does not
> subscribe to the breakable-prop forward, must receive exactly one matching
> pre/post pair for one real pipe-bomb creation and detonation. Breaking a real
> propane physics prop must still complete its engine break lifecycle, but must
> not dispatch either pipe-bomb forward family. This isolation must hold on the
> first map after a normal plugin load without an administrative detour refresh.

> **[#LH-264] campaign-score post forward.** One call to
> `L4D_SetCampaignScores(120, 340)` must dispatch one pre forward with those
> original values. If the pre subscriber changes them to `(131, 362)` and
> returns `Plugin_Changed`, the engine call must complete and the post forward
> must run once with `(131, 362)`. The post callback receives ordinary values;
> this path must not report `Invalid parameter or parameter type`.

> **[#LH-271] melee information after map start.** Once the first map is live,
> `L4D2_GetMeleeWeaponIndex("fireaxe")` must identify the map's real definition.
> Its float damage, integer damage flags, and boolean decapitation attribute must
> be readable and stable. A temporary float-damage update must round-trip and the
> original value must be restorable. These documented calls must not fail with an
> unavailable/null SDKCall on a normal plugin load.

> **[#LH-278] cancel/re-stagger lifecycle.** A live Special Infected can be
> staggered, have that stagger cancelled, and then receive a new real stagger
> either immediately in the same frame or on the following frame. The new
> stagger must remain active through the next two frames; its animation must not
> be forced instantly to its completed cycle by cleanup left over from the
> cancelled stagger. Once cancellation has completed, later ordinary staggers
> must continue to work normally.

> **[#LH-284] never-picked-up gas-can forwards.** Damaging a physical gas can
> that has remained in the world and has never entered a survivor's inventory
> must dispatch exactly one matching `L4D2_CGasCan_EventKilled` pre/post pair.
> Both callbacks must identify that gas can and preserve the real inflictor and
> attacker. An ordinary physics prop with a different model must not dispatch
> this forward family. Keep the existing picked-up gas-can behavior and the
> documented blocking/change semantics intact.

> **[#LH-291] entity addresses outside the networked-edict subset.** For every
> live engine entity index, including a valid entity that is not currently a
> networked edict, passing `GetEntityAddress(entity)` to
> `L4D_GetEntityFromAddress` must recover that same index. Repeated lookups must
> be stable, and the null address must continue to return `-1`. Do not change
> the entity or allocate a replacement as a side effect of this lookup. Server
> diagnostics show that enumerating `IsValidEdict` accounts for all of the
> successful lookups and all valid non-edicts still return `-1`; that scan can
> therefore never implement this contract. Recover the low entity index from
> the entity's embedded engine handle instead, deriving layout information from
> runtime SourceMod metadata rather than a fixed platform address. On this
> frozen engine, `m_RefEHandle` is not exposed by `FindDataMapInfo`, and
> `m_iEFlags` is not a reliable adjacent anchor. The exposed `m_angRotation`
> datamap field is the portable anchor: the embedded handle begins immediately
> after that three-float vector. Decode the complete entity-entry field. A
> live server-only entry and a networked edict are equally valid results;
> retain the null/invalid
> behavior described above. Resolve this lazily when the native is
> called after map start: entity zero is not a valid datamap probe during plugin
> startup.

> **[#LH-298] short lobby reservation cookies.** Calling
> `L4D_SetLobbyReservation` with a hexadecimal cookie of eight digits or fewer
> must not index before the input buffer or raise a native error. Preserve the
> existing ABI's word placement: setting `"1"` reads back as `"100000000"`.
> A full `"123456789ABCDEF0"` cookie must round-trip exactly, and restoring the
> prior cookie after these calls must remain safe.

## Task

Diagnose and repair all twelve reports. Preserve all unrelated natives, forwards,
gamedata loading, L4D1 compatibility and the SourceMod library registration
surface. Equivalent implementations are accepted; private function names and the
reference patch are not part of scoring.

Keep the submission source-only. Do not add `.smx` files, native libraries,
archives, symbolic links, Git metadata or vendored game files. Do not modify
anything under `/tests`.

Run the public check after editing:

```bash
python3 tools/smoke.py
```

It validates the package and compiles `left4dhooks.sp` with pinned SourceMod
`1.12.0.7246`; it contains no target assertions. After the agent exits, the private
verifier recompiles the submitted library and loads it in a real headless L4D2
dedicated server. It exercises engine AmmoDef memory, actual projectile creation
and breakage, unpicked gas-can damage, animation callbacks, and controlled
infected clients through the published include. A crash, missing forward or
incomplete case run is a failure rather than an implicit pass.

Documentation accuracy remains a manual review requirement. Automated scoring checks the public float ABI and runtime behavior; it does not grade comment wording or layout.
