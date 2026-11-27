# Write a mod: summon your horse anywhere

You are writing a **new** SMAPI mod for Stardew Valley. A skeleton project is at
`/app/mod/SummonAnywhere` — a manifest, a `.csproj` wired to the game and SMAPI,
and an empty `ModEntry`. Everything else is up to you.

## Requirement

In the base game, the [horse flute](https://stardewvalleywiki.com/Horse_Flute)
summons your horse to you, but the game refuses to do it when you are indoors —
inside your farmhouse, a shed, a cave, or the mines. Players want it to work
everywhere.

Your mod must make using the horse flute summon the player's horse to the
player's current location **even when that location is indoors**, bringing the
horse next to the player the same way it does outdoors.

Everything else about summoning must keep working exactly as the base game does
it. In particular:

- Using the flute outdoors must behave as it always has.
- The other conditions the game places on summoning a horse still apply — you are
  removing the indoor restriction specifically, not disabling the feature's rules.
- The mod must not summon a horse on its own; it happens when the flute is used.

## Notes

- The game is Stardew Valley 1.6.15 with SMAPI 4.1.10, installed at `/opt/stardew`.
  Its assemblies are referenced by the skeleton project, and
  [Harmony](https://harmony.pardeike.net/) is available if you want it.
- Build with `dotnet build mod/SummonAnywhere/SummonAnywhere.csproj -p:GamePath=/opt/stardew`.
- Keep the manifest's `UniqueID` and `EntryDll` as they are — SMAPI loads the mod
  through them, and the grading harness relies on the assembly name.
- Do not modify anything under `/tests`.
- The grading harness compiles your mod, loads it into the real game headless with
  a save that has a horse, and uses the flute both outdoors and indoors, checking
  where the horse ends up.
