# Maintenance notes: towncrier-timed-announcements

## Task

Construct task: the model writes the whole TownCrier plugin: announcement groups in
`announcements.yml`, validation with exact reasons, MiniMessage rendering with placeholders,
one `Server#broadcast(Component, String)` per announcement, per-group scheduler timers,
sequential and shuffle order, positions, pause and resume, file editing and reloads that never
leave an old timer running.

## Skeleton

Frozen `pom.xml`, minimal `plugin.yml`, empty `TownCrierPlugin`. The empty skeleton builds and
enables; the `nop` control is complete and fails every case but the sentinel.

## Reference

`solution/after/` (about 480 lines of Java): `Group` (position, cycles, timer handle),
`Announcer` (loading, validation, timers, rendering, saving), `CrierCommand` and
`TownCrierPlugin`, plus the default `announcements.yml` resource.

## Live-server design

- 20 cases in `tests/suite/TownCrierSuite.java` including the sentinel; six are ticked
  `GcbScript` cases.
- Receivers: the grader subscribes two of its own senders with
  `PluginManager#subscribeToPermission` (strong references are kept: the subscription map is
  weak). One holds `bukkit.broadcast.user`, the other also `towncrier.staff`.
- Timing is measured in ticks. A timer started in tick T announces at T + 20 x interval; every
  check sits 10 ticks away from an announcement tick (for example 30 and 50 ticks after a
  2-second group starts), so scheduler ordering inside a tick never matters.
- Ticked cases end by reloading an empty group list so no timer outlives its case.
- Group names avoid YAML 1.1 booleans (`on`, `off`, `yes`, `no`), which Bukkit's YAML reads as
  booleans.

## Fairness review

- The exam states the delivery API, the tick-based timing, the first-announcement delay, the
  position rules, the validation order and reasons, the reply formats and the saving rule.
- The shuffle case checks only the property the exam states (every message once per cycle),
  so a sequential order also satisfies it.
