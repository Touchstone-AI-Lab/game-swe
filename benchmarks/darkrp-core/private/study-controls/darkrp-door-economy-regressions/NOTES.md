# E0 notes: garrys-mod/darkrp/darkrp-door-economy-regressions

Private maintenance material. Never copy into an attempt or a model workspace.

Layout: the workspace holds `darkrp/`, so every patch here is written against `/app`
(paths start with `darkrp/`) and applied with `patch -p1` from `/app` (`root` = `.`).
Reference = starter + `solution/after/` copied over `/app/darkrp/` (the task's own
`solve.sh`).

## Baseline

| tree | result |
| --- | --- |
| starter | 2 of 11 cases pass: `sentinel: the gamemode is loaded`, `P: ordinary prices are unaffected` |
| reference | 11 of 11 |

## Preserved contracts

One, stated publicly in `## What to do`, Notes bullet 4: "Behaviour that already works
must keep working - several of these live next to code paths that are fine" (clause
`Task-preserve`).

- `P: ordinary prices are unaffected` passes in the unchanged starter: with 500 in the
  wallet `Player:canAfford(100)` is true and `canAfford(600)` is false. The behaviour
  is discoverable from `gamemode/modules/money/sh_money.lua` and its stub in
  `money/sh_interface.lua`. It is also the positive boundary of the #6218 fix, so the
  case is marked `overlap: true` with `preserved` as its primary role (decided by the
  baseline: it is `P` in `starter.execution.json`).
- `Task-preserve` is `weak`: one working path next to one of nine defects. The refusal
  halves inside Q, S, V and W also hold in the starter, but they sit inside target
  cases that fail there, so they are not separate preserved evidence.

## Controls

| control | kind | base | change | observed |
| --- | --- | --- | --- | --- |
| `target-negative-team-door` | target-negative | reference | group W reverted: `canLockUnlock` loses its per-team clause | fails exactly `W: a job assigned to a door can lock it`; admissible |
| `target-negative-allow-list-open` | target-negative | reference | `isKeysAllowedToOwn` returns true for everyone (the over-permissive mutant of `validation/per-defect-matrix.md`) | fails exactly `R: a door's allow list decides who may take it`; admissible. Re-confirms `run-85f0b7a1437d4378` |
| `compat-negative-price-ignored` | compat-negative | reference | one expression changed in `canAfford`: the negative-price guard stays, the price is no longer subtracted from the balance | fails exactly the preserved case `P: ordinary prices are unaffected` (600 becomes affordable with 500); every target case, including `P: a negative price is never affordable`, passes; admissible |
| `alternative-independent-fix` | alternative | starter | own fix for all nine reports, see below | 11 of 11; admissible |
| `alternative-strict-reading` | alternative | starter | same as above, but `isKeysOwnedBy` compares `doorData.owner` with the UserID | fails exactly Q; NOT admissible by design, kept as evidence (see below) |

The compat-negative models a repair of #6218 that closes the exploit and breaks the
ordinary affordability check next to it: the requested behaviour (no negative price is
affordable) works, the pre-existing behaviour (a price above the balance is refused)
does not.

### `alternative-independent-fix` versus the reference

Written from the public reports and the supplied source only.

- #6218 (P): an explicit early `if amount < 0 then return false end` instead of folding
  `math.floor(amount) >= 0` into the return expression.
- #6221 (Q): `isKeysOwnedBy` compares `self:getDoorOwner()` with the player directly.
- #6224 (R): reads the allow list through the existing `getKeysAllowedToOwn()` getter
  and indexes it by `UserID`.
- #6239 (W): `canLockUnlock` rewritten as three explicit early-return rules (owner,
  door group, door teams) that always returns a boolean, instead of extending the
  `or` chain.
- #6227 (S): builds a set `{[team] = true}` from the first argument and the varargs;
  the predicate is a set lookup rather than `table.HasValue` over a list.
- #6230 (T): lower-cases once into a local, stores under it and writes it back to
  `tbl.command`.
- #6233 (U): builds the `ManagersByKey` set before the agenda table is created rather
  than filling it in the manager loop.
- #6236 (V): early return on `self.IsSpawnedMoney`.
- #6242 (X): a different place. The reference teaches the generic `removeCustomItem`
  about `item.cmd`; the alternative turns `DarkRP.removeEntity` into an explicit
  function that removes `entity.cmd` and then delegates to `removeCustomItem`.

### `alternative-strict-reading`

Only `isKeysOwnedBy` differs: it reads the door data and returns true when
`doorData.owner == ply:UserID()` or the UserID is in `doorData.extraOwners`. In the
engine this is equivalent to the reference, because `getDoorOwner()` is
`Player(doorData.owner)` (`doorsystem/sh_doors.lua:45-50`) and `keysOwn` stores
`doorData.owner = ply:UserID()`. The Q stand-in (`tests/suite.lua:94-103`, `fakeDoor`
at 54-67) exposes the owner only through an overridden `getDoorOwner()`; its data table
is `{ extraOwners = {} }` with no `owner`. The implementation is therefore rejected by
the fixture, not by the behaviour. The assertion was not changed.

## Exclusion recommendations

- Exclude `Notes-causes` (not observable) and `Notes-tests` (process constraint).
- `[#6236]` deserves a reader's caveat rather than exclusion: with the shipped config
  the reported symptom does not reproduce (dropped money already has the configured
  class), and the case accepts only the `IsSpawnedMoney` flag mechanism. Failures on V
  should not be read as "the agent ignored a reproducible report".
- No task-level exclusion.

## Not run / not done

- Two of nine groups have a target-negative (W, R); the other single-group rows of
  `validation/per-defect-matrix.md` remain evidence from before the runner-collector
  replacement.
- No control for the group P mechanism constraint (fix outside `canAfford`) or for the
  group V class-name reading; both are documented in `clause-map.json` only.
- All runs used the managed GLuaTest container on this Linux host through
  `rhenium-study e0 run`. Nothing was run on Windows.

## Files

`.gitattributes` in this directory only switches off whitespace checking for the
serialized `*.patch` files (unified-diff blank context lines are a single space), the
same policy the root `.gitattributes` applies to the pack's `gold.patch`.
