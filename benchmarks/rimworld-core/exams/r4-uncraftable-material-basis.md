# Restore the material basis for uncraftable gear

R⁴ can recycle, repair and clean ordinary craftable equipment, but uncraftable
reward and ultratech gear has no crafting cost list. Those items currently produce
no usable material basis, so the operations either yield nothing or require no
materials.

Repair the supplied C# source under `R4/Source`.

Required behavior:

- Add `public static List<ThingDefCountClass> ResolveMaterialBasis(Thing item)`
  as the shared, directly callable material-basis API.
- If `CostListAdjusted(item.Stuff, errorOnNullStuff: false)` returns a non-empty
  list, return that adjusted list directly and unchanged. It takes precedence over
  every extension.
- Otherwise, return a non-empty `R4MaterialCostExtension.materials` list directly
  and unchanged. A missing extension, `materials = null`, or an empty list falls
  through to synthesis.
- Synthesis uses the item definition's abstract `MarketValue`, never an instance
  sale price. In single-precision arithmetic, compute
  `target = max(0, MarketValue) * 0.15f`, divide by
  `max(0.01f, bulkMaterialAbstractMarketValue)`, then apply
  `Mathf.RoundToInt`. Half-integers use Unity's nearest-even behavior. Return at
  least one unit of the bulk material.
- Treat `TechLevel.Undefined` as Industrial. Spacer, Ultra, and Archotech use
  Plasteel plus exactly two spacer components. Industrial uses Steel plus exactly
  two industrial components. Medieval, Neolithic, and Animal use Steel with no
  component entry.
- `GetRepairCycleCost` and `GetCleanCost` must consume the resolved basis while
  retaining their existing, separate formulas. Repair continues to use
  `repairHpPerCycle`, its strict total-cost threshold, and highest-count fallback;
  cleaning continues to use `cleanCostFraction`. Changing one setting must not
  change the other operation.
- Preserve all unrelated R⁴ behavior.

This is deliberately a material-basis subtask. It does not score random recycling
yield, map placement, operation eligibility, `DoRecycleProducts`, or
`SpawnPartialReclaim`, and a pass does not claim to restore or validate all of R⁴
v1.48.

Do not add RimWorld, Unity or Harmony binaries, generated build output, test-result
files, credentials or Workshop content. The private evaluator supplies the pinned
assemblies, compiles the source, and runs the behavior checks in the real game with
networking disabled.
