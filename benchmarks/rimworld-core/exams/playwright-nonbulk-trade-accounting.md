# Account for sold non-bulk trade goods

The supplied source is the unmodified upstream base for a bounded RimWorld 1.6
production regression in Playwright. Repair the behavior described below in
`Playwright/Source`. The task uses RimWorld Core plus Harmony only; do not add
DLC or another Mod dependency.

Required behavior:

- In the prefix, capture ThingDef and CountToTransferToDestination only for PlayerSells actions with an actual colony or trader thing.
- In the postfix, ignore empty state, non-positive counts, and missing scenarios.
- Notify every sell-items win-condition part exactly once using the captured definition and positive count, including non-bulk goods removed by ResolveTrade.
- Notify faction-specific parts only when the active trader has a faction, passing that exact faction.
- Preserve bulk-item accounting and avoid counting purchases, zero transfers, null sessions, or unrelated scenario parts.

The scored surface is `Tradeable_ResolveTradePatches Prefix/Postfix`. Keep unrelated upstream behavior intact.
Do not add RimWorld, Unity or Harmony binaries, generated output, test results,
credentials, Workshop content, assets, saves, or logs. The private evaluator owns
the pinned references and expected results and runs with networking disabled.
