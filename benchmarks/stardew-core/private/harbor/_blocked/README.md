# Blocked tasks

Authored tasks that are **not shippable**: they do not discriminate yet, or their
discriminator is unreachable with the current harness. They live here — outside the
shippable set — so a blocked task can never be mistaken for a validated one, the
same way the DarkRP suite moved its demonstrated-bad ablation out of the task
directory.

Each entry states what blocks it and what would unblock it. Do not run these as
benchmark tasks.

## `stardew-automate-incubator-egg-theft`

Real upstream bug (Automate `d336d22a`, reverted from 2.6.1): Automate reports an
incubator as done while the egg is still incubating and moves the egg into a
connected chest, so it never hatches.

**Blocked on:** a multi-phase (multi-boot) verifier. Measured, not assumed:

| probe | result |
|---|---|
| after the player drop-in action | `minutesUntilReady=9000, readyForHarvest=false, isIncubator=true` |
| after `location.DayUpdate(day+1)` ×1 and ×6 | unchanged — `DayUpdate` does not drive machine countdowns |
| after `Object.minutesElapsed(9000)` | `minutesUntilReady=0`, **`readyForHarvest` still false**, `OnlyCompleteOvernight=true` |
| after further automation cycles | `minutesUntilReady=-10`, `readyForHarvest` still false |

Automate's `GetGenericState()` returns `Done` only when `readyForHarvest` is true,
and for an `OnlyCompleteOvernight` machine the game sets that flag only inside the
real overnight sync (`Game1.newDaySync`). So the state the bug needs is unreachable
in one boot, and both trees pass the suite identically (validated: base reward 1,
oracle reward 1 — no discrimination).

**What unblocks it:** an `advance-day` harness mode plus a `tests/test.sh` that boots
the game more than once — set up and save, advance N days (one boot each), then a
final boot that loads and asserts. This is known-feasible rather than speculative:
the existing `gen-save` mode already calls `Game1.NewDay(0f)` successfully from
`GameLaunched` and writes a save, i.e. outside the tick loop, which is exactly where
the in-suite day rollover fails (SMAPI's `UpdateTicked` does not fire during
`Game1.NewDay`, so a tick-driven suite can never observe it complete).

## `stardew-cp-legacy-load-migration`

Real upstream fix (Content Patcher `76533d08`+`ccbf4ab1`, CP 2.0.6): a pre-1.6 pack
that `Load`s a legacy asset wipes every 1.6-only entry instead of merging into it.
The strongest game-version-migration candidate found in mining.

**Blocked on:** a base tree that compiles against the pinned game. CP 2.0.5 targets
SDV 1.6.3-era APIs and fails against 1.6.15 (`TokenSaveReader.cs`:
`SaveablePair<int, long>[]` has no `TryGetValue` — the game changed the type). The
obvious workaround, reverse-applying the fix onto a modern CP tag, does not apply:
the migration files were restructured between 2.0.5 and 2.5.3, and 2 of 3 hunks
conflict in both `Migration_2_0.ForObjectInformation.cs` and `...ForWeapons.cs`.

**What unblocks it:** either pin a second, older game build for CP-era tasks (the
acquisition script already supports manifest pinning, so a per-task game version is
a build-arg away), or hand-port the two fixes onto a current CP release and
re-derive the gold patch from that port rather than from upstream diffs.

## `stardew-automate-thirdparty-conflict`

The one task designed so its answer was **not** recoverable from the mod repository:
a second mod ("Smart Machines") ships as a compiled assembly only — built at image
build time, source deleted — Harmony-postfixes `Object.GetMachineData` and throws for
kegs. The premise was that the exception would escape Automate's location scan and
stop all automation, and that Automate should isolate per-entity failures.

**Blocked because the premise is false.** Automate 2.6.1 already does exactly that.
The exception fires as designed (twice in the base run's log) and Automate absorbs it:

```
[ERROR Automate] Failed to automate machine 'Keg' at Farm (tile: 10, 20). An error
occurred while setting its input. Machine paused for 30s.
[ERROR Automate] Failed getting machine for location [Farm] and tile (10, 20) and
object [(BC)12] ("Keg"). Technical details:
   at ...MachineGroupFactory.TryGetEntityWithErrorHandling(...)
```

`TryGetEntityWithErrorHandling` is a purpose-built wrapper for this case, and
`ModEntry` additionally wraps location updates and machine processing in
`HandleError`. Bystander machines keep working on the base tree, so base and oracle
both score 1 — no discrimination. Validated at each of three iterations; the guard in
`cfrun.sh` aborted before spending any model quota each time.

**What this measured:** a mature, actively-maintained mod has already absorbed the
realistic robustness defects. That is a large part of *why* tasks built from such a
mod are hard to make hard — the obvious failure modes were fixed years ago by the
maintainer, and what is left is either identifier-level (trivial) or was never a real
defect.

**What would unblock it:** target a robustness gap that upstream genuinely has, found
by auditing for unguarded third-party entry points rather than assuming one exists;
or use a less mature mod as the base, accepting the fairness cost that its contracts
are less well documented.

## `stardew-summon-horse-anywhere` — the suite's first GENERATION task (unfinished)

> **Historical.** This generation task was later completed and ships as
> `stardew-valley/core/stardew-summon-horse-anywhere` (removed in catalog 1.2.0,
> restored unchanged in 1.3.0). This section records its earlier unfinished state.

This is category one of the proposal ("mod generation, in which an agent implements a
new mod from a natural-language requirement"), which the rest of this branch does not
cover — everything else is category two (debugging). The task is fully authored:
empty mod skeleton, natural-language requirement derived from the upstream mod's
README, reference solution kept out of the environment, and a behavioural suite that
names no technique or patch target.

**Blocked on one unresolved harness question**, three iterations in:

| iteration | base / oracle | diagnosis |
|---|---|---|
| 1 | 0 / 0 | the flute's outdoor sentinel failed on both trees |
| 2 | 0 / 0 | root cause found by decompiling: `Object.performUseAction` returns immediately unless `Game1.player.canMove`, and its internal `flag` also needs `!Game1.fadeToBlack`. The suite used the flute too soon after `warpFarmer`. Fixed with a `CanUseItems()` readiness gate. |
| 3 | 0 / 0 | the readiness gate now passes, so the game accepts the item use — but the horse still does not arrive on either tree |

**Next diagnostic (not yet run):** the vanilla flute path plays a ~1.5 s animation, then
`DelayedAction.functionAfterDelay(...)` re-checks the restrictions and fires
`Game1.player.team.requestHorseWarpEvent`. Probe whether that delayed action runs and
whether the net event is processed at all in a headless single-player boot. If the net
event is the blocker, drive the summon through whatever the event handler calls
instead — still a game entry point, so the task stays implementation-agnostic.

Nothing here suggests the task design is wrong; the requirement, the isolation, and
the sentinel are all sound. It is the same class of harness-reachability question that
`stardew-automate-incubator-egg-theft` hit, and it is answerable with one probe run.
