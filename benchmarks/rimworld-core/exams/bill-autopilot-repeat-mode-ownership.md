# Preserve foreign bill repeat-mode ownership

The supplied source is the unmodified upstream base for a bounded RimWorld 1.6
production regression in Bill Autopilot. Repair the behavior described below in
`BillAutopilot/Source`. The task uses RimWorld Core plus Harmony only; do not add
DLC or another Mod dependency.

Required behavior:

- Treat every non-null repeat mode other than TargetCount, Forever, and RepeatCount as foreign-owned.
- Do not flatten a foreign mode into an Autopilot mode when capturing UI drift.
- Before deleting an owned automatic bill, remember its foreign repeat-mode defName together with compatible external bill memory.
- When recreating the bill, restore a resolvable remembered foreign mode and let its own ShouldDoNow determine materialization and retirement.
- Preserve TargetCount, Forever, RepeatCount, unresolved-mode, busy-bill, name, linked-group, serialization, and normal Autopilot target/floor behavior.

The scored surface is `AutoBillSync, BillMemory, and RecipeProbe repeat-mode lifecycle`. Keep unrelated upstream behavior intact.
Do not add RimWorld, Unity or Harmony binaries, generated output, test results,
credentials, Workshop content, assets, saves, or logs. The private evaluator owns
the pinned references and expected results and runs with networking disabled.
