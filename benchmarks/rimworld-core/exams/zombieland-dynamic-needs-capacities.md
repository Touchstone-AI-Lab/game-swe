# Respect dynamic need maxima and enhanced capacities

The supplied source is a reproducible MIT upstream source slice for a bounded
RimWorld 1.6 production regression in Zombieland. The need, capacity and no-pain
patch bodies are retained; unrelated Mod startup and asset integrations are excluded. Repair the behavior described below in
`Zombieland/Source`. The task uses RimWorld Core plus Harmony only; do not add
DLC or another Mod dependency.

Required behavior:

- For infected colonists and other already-protected need cases, replace an incoming CurLevel value with exactly one half of the need instance's current MaxLevel.
- Re-evaluate MaxLevel on every setter call; do not assume a normalized maximum of one.
- For living infected colonists and ZombieSymbiants, preserve an observed capacity above one and raise an observed capacity below one to one.
- Do not change capacities for dead or unrelated pawns and do not change unrelated needs.
- Preserve the existing membership, mood-benefit, food/rest-benefit, and no-pain decisions; UI display clamping is outside the scored scope.

The scored surface is `Need_CurLevel_Patch and PawnCapacitiesHandler_GetLevel_Patch`. Keep unrelated upstream behavior intact.
Do not add RimWorld, Unity or Harmony binaries, generated output, test results,
credentials, Workshop content, assets, saves, or logs. The private evaluator owns
the pinned references and expected results and runs with networking disabled.
