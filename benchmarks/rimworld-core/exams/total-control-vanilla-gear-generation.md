# Preserve vanilla quality and hit points without overrides

The supplied source is the unmodified upstream base for a bounded RimWorld 1.6
production regression in Rimsential - Total Control: Continued. Repair the behavior described below in
`TotalControl/Source`. The task uses RimWorld Core plus Harmony only; do not add
DLC or another Mod dependency.

Required behavior:

- When a requirement explicitly specifies quality, apply it unchanged.
- Otherwise generate quality through QualityUtility.GenerateQualityGeneratingPawn using the pawn kind and generated thing definition.
- For Core-only fixtures, do not invent a Royalty minimum or require a royalty tracker.
- When the thing uses hit points, draw the pawn kind's gearHealthRange and set at least one hit point when the drawn factor is below one.
- Preserve full hit points when the health factor is one, and preserve style, color, material, biocoding, apparel/weapon type checks, and unrelated generation behavior.

The scored surface is `ApparelGenPatch and WeaponGenPatch gear construction`. Keep unrelated upstream behavior intact.
Do not add RimWorld, Unity or Harmony binaries, generated output, test results,
credentials, Workshop content, assets, saves, or logs. The private evaluator owns
the pinned references and expected results and runs with networking disabled.
