# E0 notes: garrys-mod/darkrp/darkrp-release-regressions-v3

Private maintenance material. Never copy into an attempt or a model workspace.

Layout: the workspace holds `darkrp/`, so every patch here is written against `/app`
(paths start with `darkrp/`) and applied with `patch -p1` from `/app` (`root` = `.`).
Reference = starter + `solution/after/` copied over `/app/darkrp/` (the task's own
`solve.sh`).

## Baseline

| tree | result |
| --- | --- |
| starter | 1 of 10 cases pass: `The gamemode is loaded` only |
| reference | 10 of 10 |

## Preserved contracts

None is asserted. The exam states one ("Behaviour on the paths that already work must
not change", `## Task`, sentence 2; clause `Task-preserve`), but the only case that
passes in the unchanged starter is the load sentinel, which is fixture evidence
(`runtime-sentinel`), not evidence for a working code path. Consequently:

- no `compat-negative` control is written for this task;
- `Task-preserve` is `unasserted` and excluded;
- the task can enter general completion only, not the preserved-contract analysis.

## Controls

| control | kind | base | change | observed |
| --- | --- | --- | --- | --- |
| `target-negative-job-id` | target-negative | reference | group E reverted: `DarkRP.createJob` returns the undefined global `Team` again (`sh_createitems.lua`) | fails exactly `E: creating a job hands back the team number`; admissible |
| `target-negative-shipment-store-half` | target-negative | reference | store half of masking pair F reverted: `createShipment` indexes the raw name while `getShipmentByName` still lower-cases | fails exactly `F: a shipment created with mixed case is found by its lower-case name`; admissible. Confirms the half-fix row of `validation/per-defect-matrix.md` on the current evaluator |
| `alternative-independent-fix` | alternative | starter | own fix for every report, see below | 10 of 10; admissible |
| `alternative-strict-reading` | alternative | starter | same as above, but group B keys the wake on the physics-init result | fails both B cases; NOT admissible by design, kept as evidence (see below) |

### `alternative-independent-fix` versus the upstream reference

Written from the public reports and the supplied source only.

- #4423: the reference walks the module-local `arrestedPlayers` SteamID set with
  `next()` and derives list and count from the iterator. The alternative makes the
  list the primitive (`player.GetAll()` filtered by `ply:isArrested()`), iterates over
  a snapshot of it and takes the count from it; stubs are published in
  `police/sv_interface.lua` like the rest of the police API.
- #4415: `IsValid(phys)` early return / wake-last ordering in `spawned_ammo` and
  `spawned_weapon`, plus the same guard in `spawned_shipment/commands.lua` and
  `sv_purchasing.lua`. It does not add the reference's `ents.Create` failure handling
  or PlayerUse rollback (unreported since the report was trimmed).
- #4418: a shared `weaponArgument` validator that reports usage through
  `FAdmin.Messages.SendMessage`, instead of an inline guard.
- #4421: `destroyQuestion` takes the entry out of the table first and only notifies
  the client when there was one.
- #4424: returns `CustomTeam.team`.
- #4431: a different strategy. The reference lower-cases both the index key and the
  lookup key. The alternative leaves the index untouched (exact display name, so
  `removeShipment`'s `shipByName[ship.name] = nil` keeps working) and adds a
  case-insensitive fallback scan over `CustomShipments` in `getShipmentByName`.
- Unreported haystack (voice-cache hook name, food sound, FAdmin teleport/ragdoll/slay
  and money-printer validity guards) is left untouched.

### `alternative-strict-reading`

Group B only differs: `local hasPhysics = DarkRP.ValidatedPhysicsInit(...)` and the
physics object is woken only when that returned true. In the engine this is a correct
fix for #4415: `ValidatedPhysicsInit` returns the result of `ent:PhysicsInit()`, and
the only way to get an invalid physics object is for that call to fail. The suite's
stand-in (`tests/suite.lua:47-50`, `57-62`) returns `true` from `PhysicsInit` AND
`NULL` from `GetPhysicsObject`, a state the engine does not produce, so this
implementation errors inside the stand-in and both B cases fail. This is an
over-constraining fixture, not a defect of the implementation. The assertion was not
changed; the passing alternative uses `IsValid(phys)`.

## Exclusion recommendations

- Exclude clause `Task-preserve` (no assertion) and `[#4423]:published` (no case looks
  at the published stubs).
- Treat `[#4423]:agree` as weak: agreement is only observed with nobody arrested.
- The task itself is usable for general completion. It should not be used for any
  preserved-contract measurement.

## Not run / not done

- No compat-negative (none is possible, see above).
- No control for the group G observer constraint (feedback is only seen through
  `FAdmin.Messages.SendMessage`); it is documented in `clause-map.json` only.
- All control runs used the managed GLuaTest container
  on this Linux host through `rhenium-study e0 run`. Nothing was run on Windows.

## Files

`.gitattributes` in this directory only switches off whitespace checking for the
serialized `*.patch` files (unified-diff blank context lines are a single space), the
same policy the root `.gitattributes` applies to the pack's `gold.patch`.
