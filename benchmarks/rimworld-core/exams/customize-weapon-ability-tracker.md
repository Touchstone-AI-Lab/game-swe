# Manage weapon abilities when a pawn has no tracker

The supplied source is the unmodified upstream base for a bounded RimWorld 1.6
production regression in Customize Weapon. Repair the behavior described below in
`CustomizeWeapon/Source`. The task uses RimWorld Core plus Harmony only; do not add
DLC or another Mod dependency.

Required behavior:

- Create Pawn_AbilityTracker lazily when an equipped pawn has no tracker and a managed ability must be synchronized.
- Do not create a tracker when there is no current holder or no managed ability definition.
- Add each managed ability once, update its reloadable properties, and preserve unrelated abilities.
- Capture managed cooldown and charge state before unequip or replacement, then restore it after reequip or post-load synchronization.
- Remove abilities no longer managed, prune stale stored state, tolerate null/duplicate properties, and preserve reload behavior.

The scored surface is `CompAbilityProvider managed ability lifecycle`. Keep unrelated upstream behavior intact.
Do not add RimWorld, Unity or Harmony binaries, generated output, test results,
credentials, Workshop content, assets, saves, or logs. The private evaluator owns
the pinned references and expected results and runs with networking disabled.
