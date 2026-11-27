# Maintenance notes: payload-and-save-regressions

## Upstream

- Repository: https://github.com/Anuken/Mindustry (GPL-3.0, `LICENSE` kept).
- Base: release tag `v159.7`, commit `c9686eb5d0ae5dd47ee02c40f99f7d5018ccbc8c`.

| Report | Upstream fix | In v159.7? | Starter | Reference |
| --- | --- | --- | --- | --- |
| payloads come off derelict payload conveyors after loading | `3b29a4877f6732e47941a71c3dd5d63bdfbf5054` (issue #12354) | yes | reverted | as released |
| saves with 1000+ queued plans cannot be loaded | `54443b9517eef7ea9acb7a283cd932e5e7660b47` | yes | reverted | as released |
| carried derelict blocks cannot be set down near a core | `1e8317fbac4c8ce2509eac7a758f4f846c4c00d3` (issue #12683, first released in v160.5) | no | as released | fix applied |

Every reverted defect shipped in a release before its fix: the plan-queue limit was
introduced by `4851440c1` ("Network serialization size limit fixes", first released in
v156) and fixed in v158; the payload-conveyor defect was fixed in v159.5. No defect is
injected. `solution/after` holds `PayloadConveyor.java`, `TypeIO.java` and
`Build.java`.

## Defects

- `PayloadConveyor`: `noUpdateDisabled = true` plus an early return for disabled
  conveyors means a derelict (always disabled) conveyor never calls `updatePayload()`,
  and `read()` discards the saved progress, so a loaded payload stays at (0, 0).
- `TypeIO.readPlansQueue` rejects queues of `maxArraySize` (1000) or more plans, so the
  unit entity (and the save) fails to load.
- `Build.validPlaceIgnoreUnits` applies the core protection radius to derelict blocks
  dropped from payloads (`checkVisible == false`).

## Suite design

Ten cases: one sentinel, three targets, six preserved. The cases use public building and
unit APIs: `PayloadConveyorBuild.handlePayload`, `SaveIO` round trips, `Unit.plans()`,
`Payloadc.addPayload`/`dropLastPayload`, and read payload positions, plan counts and the
blocks that end up on tiles.
