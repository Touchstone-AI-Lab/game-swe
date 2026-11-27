# Content Patcher: legacy packs wipe game content after the 1.6 update

You are working on **Content Patcher**, the SMAPI framework mod that lets Stardew
Valley content packs edit game assets declaratively. The mod's source is at
`/app/StardewMods` (the mod project is `ContentPatcher/`; `Common/` is shared code
used by the same author's mods).

## Problem

Stardew Valley 1.6 reorganized many data assets (for example, the old
`Data/ObjectInformation` slash-delimited strings became structured entries in
`Data/Objects`). Content Patcher supports pre-1.6 content packs through runtime
migrations that map their old-format patches onto the new assets, so the huge
catalogue of older packs keeps working.

Since the update, players using older packs report broken games. One writes: "The
moment I add this old furniture-and-crops pack, half the items in the game
disappear. New 1.6 stuff like carrots is just gone — seeds vanish from vendors,
existing plants turn into error items, and my save won't load with some of my
items in it. Removing the pack brings everything back. The pack itself only
touches a handful of items; it worked fine on 1.5.6, and the pack author says
they never touched any of the new content."

Other reports describe the same pattern with missing display names and broken
textures for items the old pack never mentioned.

## Task

Make the runtime migration of pre-1.6 **Load** patches preserve everything the
legacy pack doesn't actually provide: content that only exists in 1.6 must
survive, and fields with no pre-1.6 equivalent must keep their vanilla values
instead of being reset. Migrated packs' own entries must still apply, and the
behavior of 1.6-format packs must not change.

## Notes

- The game is Stardew Valley 1.6.15 with SMAPI 4.1.10, installed at `/opt/stardew`.
- Build with `dotnet build ContentPatcher/ContentPatcher.csproj -p:GamePath=/opt/stardew`.
- Do not modify anything under `/tests`.
- The grading harness compiles your tree, loads it into the real game headless
  with a pre-1.6-format content pack installed, and inspects the migrated assets.
