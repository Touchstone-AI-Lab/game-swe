# Left 4 Dead 2: LinGe release regressions

You are working on **LinGe VScripts**, an MIT-licensed Left 4 Dead 2 server-side
VScript project. The project is located at `/app/linge-hud`.

## Problem

This release missed a batch of fixes. Server operators supplied the reports below.
They are observations, not diagnoses, and they do not necessarily share a cause.
One explicit preservation requirement is included because several terminal fixes
touch the same delayed-message path.

> **[#LG-417] Terminal friendly fire.** Ordinary friendly-fire totals agree, but a
> hit that incapacitates or kills a Survivor can disappear or include overkill. A
> Survivor with 30 health available who is hit for 45 should contribute 30. A
> Survivor with 12 permanent and 8 temporary health who is incapacitated should
> contribute 20. When a hit lands on exactly zero health, its delayed message must
> say that the victim died rather than describing an ordinary hit. Damage received
> by the victim and all corresponding round totals must agree with the attacker.

> **[Preservation: delayed team-hurt messages.]** Keep the existing pair-scoped
> behavior while repairing terminal hits: repeated hits for one attacker/victim
> pair aggregate into one delayed message, while different pairs remain independent.
> Self-damage and damage reported after a Survivor was already incapacitated, dying,
> or dead are not friendly fire. Terminal labels must describe the same pair and
> aggregate as their damage totals.

> **[#LG-428] Tank totals around death.** The last real-health damage is sometimes
> absent and sometimes appears twice. Operators also found that ordinary shots which
> hit a Tank after it has entered its incapacitated death transition can continue to
> inflate the Tank ranking. Across the complete transition, only real Tank health
> removed by each Survivor may be counted.

> **[#LG-433] Special-infected damage.** A qualified flame tick was logged as
> `weapon=entityflame`, `type=268435464`, and `dmg_health=4`, while the target actually
> lost 12 health; the HUD added only 4. Other weapon/type combinations still report
> their real damage directly and must not be multiplied. Terminal overkill remains
> clamped to remaining health, and stale post-death events must never subtract from
> cumulative or round totals.

> **[#LG-439] Campaign totals after a failed map.** With cumulative statistics and
> `discardLostRound` enabled, totals from a successfully completed map can be lost
> after the next map is failed. Replaying that failed map should discard only work
> from the failed attempt; the last successful-map totals are the rollback baseline.

> **[#LG-445] Help markers.** Incapacitated and ledge-hanging help markers can behave
> like domination markers and disappear under the domination cleanup path. Revive
> markers must share one lifecycle with each other, but not with domination markers.

> **[#LG-452] RewardHP temporary-only mode.** In mode `2`, a special-infected reward
> near the configured health limit can turn into permanent health. Mode `2` must
> grant only temporary health and clamp that reward to the remaining total-health
> capacity. Mode `3` keeps its existing behavior: use the full temporary reward when
> it fits, otherwise fall back to the configured permanent reward.

## Task

Diagnose and fix every report. Preserve behavior outside the reported paths,
including ordinary damage, kill/headshot counters, ranking and cache configuration,
the existing event integration, and the addon entrypoint.

Do not replace event handling with per-tick health polling. Preserve the upstream MIT
license and attribution. Keep the submission source-only: do not add compiled
binaries, archives, symbolic links, or Git metadata. Do not modify anything under
`/tests`.

Run `python3 tools/smoke.py` after editing. This public check validates UTF-8 Squirrel
source structure, required files, attribution, and the addon entrypoint. It contains
no private behavioral cases and is not the final verifier.

The verifier stages the submitted project as an addon and boots a real headless Left
4 Dead 2 dedicated server after the agent exits. It runs private deterministic
event/entity scenarios in the engine's Squirrel VM. Terminal scenarios drive the
project's existing pre-damage callback chain and complete hurt/incapacitation/death
event sequences; delayed messages are allowed to settle before their output is
checked. Cache checks include successful-map, restore, and failed-replay boundaries.
The verifier checks externally observable counters, messages, marker cleanup, and
configuration behavior; it does not compare the submission with the reference patch
or require private helper names.
