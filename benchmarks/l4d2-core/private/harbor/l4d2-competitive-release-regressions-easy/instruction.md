# Left 4 Dead 2 Competitive Rework: release regressions

You are working on the GPL-3.0-licensed **L4D2 Competitive Rework** SourceMod
repository at `/app/l4d2-competitive`. The snapshot contains a large collection of
real server plugins. Three operators reported regressions in this release.

## Reports

> **[#CR-101] Incapacitated empty-clip reload.** The incap-fire compatibility
> plugin still prevents shove from suppressing primary fire when an incapacitated
> Survivor has ammunition. With an empty active-weapon clip, however, it repeatedly
> moves `m_flNextSecondaryAttack` into the future, so the engine cannot begin its
> automatic-reload path. Empty clips must leave that timestamp unchanged. If the plugin applied a delay while the
> clip had ammunition, leaving incap must release that delay; clients outside the
> Survivor/incap path must remain unaffected.

> **[#CR-118] Matchmode attribute rollback.** A matchmode can change ordinary gun
> and melee attributes as well as the plugin-managed `tankdamagemult` and shotgun
> `reloaddurationmult` values. During `!chmatch`, Confogl emits
> `LGO_OnMatchModeUnloaded` before the old mode and Left4DHooks are unloaded. At
> that boundary all values owned by this plugin must be restored to the values
> saved before the outgoing mode. A second mode must therefore observe the real
> baseline, not values inherited from the first mode. Keep the existing manual
> reset command and normal config-reload behavior.

> **[#CR-126] Partial map names during forced changelevel.** SourceMod accepts a
> unique partial map name such as `c1m2`, but the forced-changelevel hook sends the
> unresolved text to the engine and the transition stalls. Resolve a valid unique
> partial name to its full installed-map name before the engine processes the
> change (for example `c1m2` to `c1m2_streets`) and use that same full name for the
> existing Director transition work. Already complete names must keep working.
> Invalid input must not be rewritten to an unrelated map. Resolution
> must also be honored when the Director reports that a transition is already in
> progress.

## Task

Diagnose and repair all three reports. Preserve behavior outside these paths,
including the existing event/forward integration, commands, Director reset work,
plugin metadata and GPL attribution.

Keep the submission source-only. Do not add `.smx` files, native libraries,
archives, symbolic links, Git metadata or vendored game files. Do not modify
anything under `/tests`.

Run the public check after editing:

```bash
python3 tools/smoke.py
```

It verifies the source package and compiles the three affected plugins with pinned
SourceMod `1.12.0.7246`; it contains no target assertions. After the agent exits,
the private verifier recompiles the submitted source and loads it with pinned
MetaMod/SourceMod in a real headless L4D2 dedicated server. It lets SourceMod
dispatch real per-tick player-command callbacks, emits Confogl's named global
unload forward, exercises engine weapon attributes and map-change boundaries, and
checks the documented timestamp/attribute/map behavior. Scoring does not compare
against a reference diff or require private helper names.
