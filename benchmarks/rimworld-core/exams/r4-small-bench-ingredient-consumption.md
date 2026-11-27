# Consume repair ingredients placed around small workbenches

The supplied source is the unmodified upstream base for a bounded RimWorld 1.6
production regression in R⁴. Repair the behavior described below in
`R4/Source`. The task uses RimWorld Core plus Harmony only; do not add
DLC or another Mod dependency.

Required behavior:

- Consume requested item stacks first from the bill giver's ingredient stack cells, ordered by distance from its interaction cell.
- If those cells do not satisfy the request, continue through vanilla-equivalent radial placement cells around the interaction cell.
- Ignore out-of-bounds cells, already visited cells, the bench itself, non-item things, and impassable edifices with no usable surface.
- Aggregate duplicate positive costs, ignore null or non-positive cost entries, consume no more than requested, and stop once all requirements are satisfied.
- Preserve large-bench behavior and all unrelated material, repair, cleaning, recycling, hauling, and placement behavior.

The scored surface is `MaterialUtility.ConsumeIngredientsOnBench`. Keep unrelated upstream behavior intact.
Do not add RimWorld, Unity or Harmony binaries, generated output, test results,
credentials, Workshop content, assets, saves, or logs. The private evaluator owns
the pinned references and expected results and runs with networking disabled.
