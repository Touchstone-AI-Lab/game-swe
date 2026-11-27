# E0 notes: garrys-mod/darkrp/darkrp-live-server-regressions

Private maintenance material. Never copy into an attempt or a model workspace.

Layout: the workspace holds `darkrp/`, so every patch here is written against `/app`
(paths start with `darkrp/`) and applied with `patch -p1` from `/app` (`root` = `.`).
Reference = starter + `solution/after/` copied over `/app/darkrp/` (the task's own
`solve.sh`).

## Baseline

| tree | result |
| --- | --- |
| starter | 2 of 11 cases pass: `sentinel: the gamemode is loaded`, `S: a real job can still be made a hitman team` |
| reference | 11 of 11 |

## Preserved contracts

One, stated publicly in `## What to do`, Notes bullet 4: "Behaviour that already works
must keep working - several of these live next to code paths that are fine" (clause
`Task-preserve`).

- `S: a real job can still be made a hitman team` passes in the unchanged starter:
  registering an existing job through `DarkRP.addHitmanTeam` and reading it back from
  `DarkRP.getHitmanTeams()` already works. The behaviour is discoverable from
  `gamemode/modules/hitmenu/sh_init.lua` and its stub in `hitmenu/sh_interface.lua`.
  It is also the positive boundary of the #5103 fix, so the case is marked
  `overlap: true` with `preserved` as its primary role (decided by the baseline: it is
  `P` in `starter.execution.json`).
- `Task-preserve` is `weak`: this is the only working path the suite looks at; the
  paths next to the other eight defects are not asserted.

## Controls

| control | kind | base | change | observed |
| --- | --- | --- | --- | --- |
| `target-negative-usergroup-signal` | target-negative | reference | group T reverted in `fadmin/access/sv_init.lua`: the previous group is read after `PlayerSetGroup` (both setroot and setaccess) | fails exactly `T: a usergroup change reports the group the player came from`; admissible |
| `target-negative-category-redeclare` | target-negative | reference | group BB reverted: `insertCategory` no longer carries `members` over when a category is re-declared | fails exactly `BB: re-declaring a category keeps what was already in it`; admissible |
| `compat-negative-hitman-load-only` | compat-negative | reference | one condition added to the reference's guard: `addHitmanTeam` also refuses every job once `DarkRP.DARKRP_LOADING` is false | fails exactly the preserved case `S: a real job can still be made a hitman team`; every target case (including `S: a job that does not exist ...`) passes; admissible |
| `alternative-independent-fix` | alternative | starter | own fix for all nine reports, see below | 11 of 11; admissible |

The compat-negative models an over-strict repair of #5103: the bogus job number stays
refused (target S passes), default hitman teams registered while the gamemode loads
keep working, but an addon registering a real job at run time is now refused, which is
exactly the behaviour that worked before the change.

### `alternative-independent-fix` versus the reference

Written from the public reports and the supplied source only.

- #5102 (T): one local helper `changeGroupAndSignal(target, newGroup)` reads the old
  group, sets the new one and signals CAMI; both command paths call it. The reference
  adds a `target_previous_group` local inline at each site.
- #5103 (S): resolves the job table once (`RPExtraTeams[job]`) and returns unless it is
  a table, then reuses it for the disabled-defaults check.
- #5105 (U): takes the entry out of `Questions` first and only sends the client message
  when an entry existed.
- #5106 (V): hoists `targetName` once and uses it for both the lookup and the
  not-found phrase. The reference's additional `#args == 0` guard is not added
  (unreported, unasserted).
- #5107 (X): removes `"vote" .. job.command` after `removeCustomItem`, and only when
  such a command exists.
- #5104 (Z): computes the id first and stores the ammo type under it
  (`gm.AmmoTypes[ammo.id] = ammo`) instead of taking `table.insert`'s return value.
- #5108 / #5109 (AA, BB): fixed in `DarkRP.createCategory` rather than in
  `insertCategory`. A helper looks up the members of an already declared category of
  the same name; the new table adopts them (BB). The weapons twin of a shipments
  category is a shallow copy with its own member list (AA), where the reference uses
  `table.Copy` and patches `insertCategory`'s override branch.
- #5110 (CC): `IsValid(phys)` early return in `spawned_money`.

## Exclusion recommendations

- Exclude `Notes-causes` (not observable) and `Notes-tests` (process constraint).
- No task-level exclusion. Readers should know the known issues in `clause-map.json`:
  the CC stand-in trap, the T observer on the `CAMI` table field, and U accepting an
  empty `destroyQuestion`.

## Not run / not done

- One target-negative per group was not attempted; two groups (T, BB) were run. The
  other seven single-group rows of `validation/per-defect-matrix.md` remain evidence
  from before the runner-collector replacement.
- No strict-reading alternative was run for the CC stand-in trap; the same construction
  is demonstrated in `darkrp-release-regressions-v3/alternative-strict-reading`.
- All runs used the managed GLuaTest container on this Linux host through
  `rhenium-study e0 run`. Nothing was run on Windows.

## Files

`.gitattributes` in this directory only switches off whitespace checking for the
serialized `*.patch` files (unified-diff blank context lines are a single space), the
same policy the root `.gitattributes` applies to the pack's `gold.patch`.
