# Write a mod: chests run the machines next to them

You are writing a **new** SMAPI mod for Stardew Valley. A skeleton project is at
`/app/mod/AutoWorkshop` — a manifest, a `.csproj` wired to the game and SMAPI, and
an empty `ModEntry`. Everything else is up to you.

## Requirement

Placing a chest **directly against** a machine (any of the four sides) should make
the chest act as that machine's storage, with no player interaction:

1. **Feeding.** When such a machine is idle and the chest holds valid input for it,
   the machine starts processing automatically, consuming the input (and any extra
   items the recipe needs, e.g. coal for a furnace) from the chest.
2. **Collecting.** When the machine finishes, the product is moved into the same
   chest automatically and the machine moves on.
3. **No item may ever be lost.** If the chest is completely full when the machine
   finishes, the product must stay safely in the machine and be delivered as soon
   as space opens up — never dropped or destroyed.
4. **Glitch tolerance.** Some machines occasionally produce a corrupted product
   with a quantity of zero. Such a product must be cleared away and the machine
   must carry on with the next batch instead of jamming forever.
5. **Everywhere.** This must work in every location — outdoors and inside farm
   buildings (sheds, coops, barns), including when the player has **several
   buildings of the same type**: each building's machines use the chest in that
   same building.
6. **No overreach.** Only a chest *directly touching* a machine participates. A
   chest two tiles away must do nothing, and machines with no adjacent chest must
   never be touched.

## Notes

- The game is Stardew Valley 1.6.15 with SMAPI 4.1.10, installed at `/opt/stardew`.
  Its assemblies are referenced by the skeleton project, and
  [Harmony](https://harmony.pardeike.net/) is available if you want it.
- Build with `dotnet build mod/AutoWorkshop/AutoWorkshop.csproj -p:GamePath=/opt/stardew`.
- Keep the manifest's `UniqueID` and `EntryDll` as they are — SMAPI loads the mod
  through them, and the grading harness relies on the assembly name.
- Do not modify anything under `/tests`.
- The grading harness compiles your mod and loads it into the real game headless.
  It exercises furnaces beside chests on the farm and inside multiple identical
  farm buildings, a full chest, a corrupted zero-quantity product, and machines
  with no adjacent chest, all against live game state.
