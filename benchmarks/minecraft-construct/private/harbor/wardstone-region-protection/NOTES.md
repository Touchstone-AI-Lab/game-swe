# Maintenance notes: wardstone-region-protection

## Task

Construct task: the model writes the whole Wardstone plugin: inclusive cuboid regions with
priorities, owners, members and allow/deny flags, flag resolution across overlapping regions
(highest priority, deny wins ties, alphabetical deciding region), enforcement on break, place,
explosion, burn and ignite events, `regions.yml` persistence and the `/ward` commands.

## Skeleton

Frozen `pom.xml`, minimal `plugin.yml`, empty `WardstonePlugin`. The empty skeleton builds and
enables; the `nop` control is complete and fails every case but the sentinel.

## Reference

`solution/after/` (about 650 lines of Java): `Flag`, `Region`, `RegionStore` (YAML and
resolution), `ProtectionListener`, `WardCommand` and `WardstonePlugin`.

## Live-server design

- 25 cases in `tests/suite/WardstoneSuite.java`, sentinel first, all synchronous.
- Events are built on real blocks and called through the plugin manager: `BlockBreakEvent`,
  `BlockPlaceEvent` (with `Player` stand-ins), `EntityExplodeEvent` (a spawned creeper),
  `BlockExplodeEvent`, `BlockBurnEvent` and `BlockIgniteEvent` with four causes. The grader
  reads cancellation, the remaining explosion block list and the messages the stand-in got.
- Each case uses its own area of the world (x from 0 to 1110), so regions of earlier cases
  never overlap later ones. The reload case replaces `regions.yml` and runs near the end.

## Fairness review

- The exam states inclusive bounds, the resolution and deciding-region rules, the exemption
  rule, the fire causes, the file layout, the reply texts and the validation order.
- `regions.yml` is read back with Bukkit's YAML parser, so flow or block style and key order
  are free; a missing empty `flags` section is accepted.
