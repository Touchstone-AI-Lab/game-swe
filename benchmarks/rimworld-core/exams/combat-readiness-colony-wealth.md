# Preserve raw colony wealth for storyteller accounting

The supplied source is a faithful RimWorld 1.6 reconstruction of the selected
upstream base behavior for a bounded production regression in Combat Readiness
Check. Repair the behavior described below in `CombatReadinessCheck/Source`.
The task uses RimWorld Core plus Harmony only; do not add DLC or another Mod
dependency.

Required behavior:

- Let RimWorld's original `Map.PlayerWealthForStoryteller` getter run for maps
  that are not player-home maps.
- Let the original getter run when the active storyteller difficulty uses fixed
  wealth mode.
- For a player-home map in normal wealth mode, replace the getter result with
  raw armoury wealth plus the configured percentage of building wealth.
- Do not pass either component through the incident-points curve; the getter
  returns wealth, not already converted storyteller points.
- Preserve the existing percentage calculation, including zero, fractional,
  full, and intentionally out-of-range configured percentages.

The scored production surface is
`MarvsMapWealthForStoryTeller.Prefix(Map, ref float)`. Keep unrelated upstream
behavior intact. Do not add RimWorld, Unity or Harmony binaries, generated
output, test results, credentials, Workshop content, assets, saves, or logs. The
private evaluator owns the pinned references and expected results and runs with
networking disabled.
