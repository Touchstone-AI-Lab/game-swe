# Use local growing conditions for cultivator planting

The supplied source is the unmodified upstream base for a bounded RimWorld 1.6
production regression in Project RimFactory Revived. Repair the behavior described below in
`ProjectRimFactory/Source`. The task uses RimWorld Core plus Harmony only; do not add
DLC or another Mod dependency.

Required behavior:

- Evaluate whether the plant can be sown at the selected cell without using the map-wide temperature shortcut.
- Require PlantUtility.GrowthSeasonNow for that exact cell and plant definition.
- Continue to reject adjacent sow blockers and unavailable seed requirements.
- Permit vacuum-resistant plants in vacuum and reject other plants when local vacuum is at least one half.
- Place exactly one plant only after every condition passes; preserve harvesting, foreign-plant removal, zone, output, and selection behavior.

The scored surface is `Building_Cultivator.TryPlantNew`. Keep unrelated upstream behavior intact.
Do not add RimWorld, Unity or Harmony binaries, generated output, test results,
credentials, Workshop content, assets, saves, or logs. The private evaluator owns
the pinned references and expected results and runs with networking disabled.
