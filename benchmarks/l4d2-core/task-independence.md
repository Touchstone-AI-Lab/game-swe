# Task identity and production-code review

Reviewed on 2026-09-21 for pack 1.2.0. These are ten distinct repair targets in
five upstream codebases, not ten independent projects or ten verbatim upstream
issues. The original tasks combine seeded and retained release regressions;
the five additions explicitly contain task-authored maintenance contracts.

| Task | Production repair surface | Executed behavior |
| --- | --- | --- |
| Competitive release | `l4d2_incap_fire_fix.sp`, `l4d2_weapon_attributes.sp`, `l4d2_fix_changelevel.sp` | Real command dispatch, match unload/reset, map resolution |
| Left4DHooks | Public include, `l4dd_natives.sp`, `l4dd_forwards.sp`, animation/SDKCall setup patches | Native ABI, engine memory, detours, forwards, callbacks |
| Infected Bots | `l4dinfectedbots.sp` | Capacity/configuration, actual replacement spawn times, finale cleanup |
| LinGe release hard-v3 | `HUD.nut`, `Hint.nut`, `RewardHP.nut` | Damage accounting, cache/final-state handling, hints, health rewards |
| Mutant Tanks | Core, primary ability aggregate, Warp/Hypno/Panic/Acid/Ammo modules | Live entities, damage/ammo, public forwards, ability and reward lifecycles |
| LinGe Director | `Base.nut`, `MoreSI.nut` | Configuration ownership, reentrant dispatch, Director option lifecycle |
| Competitive score | `l4d2_hybrid_scoremod_zone.sp` | Score/loss ledger, ledge episodes, deferred half-round ownership |
| VSLib | `timer.nut`, `easylogic.nut`, `fileio.nut`, Base serialization integration | Callback mutation, clocks, data codec, real existing Base/MoreSI callers |
| Confogl | `confoglcompmod/CvarSettings.sp` in the complete plugin | ConVar snapshots, enforcement, finite callback chains, late binding/release |
| L4D2Lib | `mapinfo.sp`, `tanks.sp`, lifecycle entry points in `l4d2lib.sp` | Map import/query/geometry and connection-safe Tank transitions |

SourcePawn verifiers compile the submitted production entry points and load
them into the dedicated server. Squirrel verifiers include the submitted mod
modules in the real VScript VM. They do not compile only a common invented
`ReleaseContract` sidecar while leaving the upstream repository unused.
Some fixtures synthesize events or substitute game entities to reach edge
states deterministically; notably LinGe hard-v3 is not a complete combat
end-to-end test. A real engine alone does not prove complete integration.

The task suites, repaired production files, and behavioral requirements were
compared during independent review. A pack test additionally rejects exact
duplicate production-reference content and identical behavior-suite sets even
when directories/files are renamed. That check is deliberately only a clone
screen: superficial edits can defeat hashes, so semantic review remains
required. Case counts are derived from each task's behavior; they are not a
fixed multiplicative rubric reused ten times.

## Shared baselines and evaluation splits

Later starters intentionally include prior repairs so they do not ask a solver
to repair the same earlier defects again:

- Competitive score, Confogl and L4D2Lib contain the accepted easy-task repairs.
- Confogl and L4D2Lib contain the accepted score repair.
- LinGe Director and VSLib contain accepted hard-v3 repairs.
- VSLib contains the accepted Director Base/MoreSI repair.

Consequently a later starter can expose an earlier answer. Keep connected
task families together when constructing training/evaluation splits and use
fresh isolated model contexts. Do not report these tasks as statistically
independent or expose all starter trees to one model while claiming a blind
attempt.

## Difficulty

The labels remain one easy, two medium and seven hard. They are author
assessments, not measured solve rates. Pack 1.2.0 fixes fairness and integration
coverage; it does not add arbitrary complexity to force lower solve rates, and it
has not been model-calibrated.

See [review revisions](review-revisions.md) for current maintainer controls,
independent reviews, and the distinction between full and focused checks.
