# Maintenance notes: defense-and-heat-regressions

## Upstream

- Repository: https://github.com/Anuken/Mindustry (GPL-3.0, `LICENSE` kept).
- Base: release tag `v159.7`, commit `c9686eb5d0ae5dd47ee02c40f99f7d5018ccbc8c`.

| Report | Upstream fix | In v159.7? | Starter | Reference |
| --- | --- | --- | --- | --- |
| idle turrets fire two quick shots | `36ca01a1a338eecda29916f6c8d2a7c0f6465400` (issue #12311) and its follow-up `907b4edbf06228b52371225300b413e62df700fc` (PR #12336) | yes | both reverted (the v159.0 code) | as released |
| disabled heat redirectors pass heat | `56defd8e02336913b6cc62566d4e8ec12db2edb4` (PR #12352) | yes | reverted | as released |
| shockwave tower hits bullets outside its circle | `abebad2f5fe9b4d2606c980ec76687666752eea8` (issue #12495, first released in v160) | no | as released | fix applied |

`907b4edbf` reworked the reload fix of `36ca01a1a` (moving the cap into `handleReload`
and gating cooling there); reverting both in reverse order restores the released v159.0
turret code, which has only the uncapped-reload defect. Both reverted defects shipped in releases (the turret fix first appeared in v159.2, the
heat-conductor fix in v159.5). No defect is injected.
`solution/after` holds `Turret.java`, `ReloadTurret.java`, `PointDefenseTurret.java`,
`HeatConductor.java` and `ShockwaveTower.java`.

## Defects

- `Turret.updateReload` keeps adding to `reloadCounter` while idle; `updateShooting`
  fires and keeps `reloadCounter % reload`, so after an idle period the second shot
  follows after the remainder (14 ticks for a duo idle for 250 ticks).
- `HeatConductor`: neighbours force `updateHeat()` on a disabled conductor, which keeps
  computing heat; the fix sets `noUpdateDisabled` and yields 0 heat when disabled.
- `ShockwaveTower.updateTile` collects every hittable enemy bullet in the square
  bounding box of its range; the fix adds a `within(range + 1)` test.

## Suite design

Nine cases: one sentinel, three targets, five preserved. Duos with copper (or silicon)
ammunition fire at enemy (crux) thorium walls under the full game simulation
(`logic.update`) with a fixed one-tick delta; shots are counted from the public
`totalShots` counter. The silicon case keeps a repair from discarding the fractional
reload remainder (a clamp to exactly the reload time lowers the fire rate). Heat is
read through a logic processor (`control enabled`, `sensor @heat`). Shockwave cases give
the tower's team the cheat rule so it runs without cyanogen and power, and create
stationary dagger bullets for the enemy team.
