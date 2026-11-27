# Automate: mini-fridges stopped working after the last release

You are working on **Automate**, a SMAPI mod for Stardew Valley that lets machines
pull input from and push output into adjacent chests automatically. The mod's
source is at `/app/StardewMods` (the mod project is `Automate/`; `Common/` is
shared code used by the same author's mods).

## Problem

Since the latest release, players report that machine setups built around
**mini-fridges** no longer do anything. A furnace next to a mini-fridge full of ore
and coal just sits there, and finished goods are no longer collected into the
fridge either. The same setups worked before updating. Regular chests and stone
chests still work fine, and players with Junimo chests or big chests say those are
fine too — it's specifically mini-fridges that machines now ignore.

The last release added a config option to choose which chest types Automate treats
as storage; a player suspects the regression came in with that change.

## Task

Make machines treat mini-fridges as storage containers again, without changing the
behavior of the other chest types.

## Notes

- The game is Stardew Valley 1.6.15 with SMAPI 4.1.10, installed at `/opt/stardew`.
- Build with `dotnet build Automate/Automate.csproj -p:GamePath=/opt/stardew`.
- Do not modify anything under `/tests`.
- The grading harness compiles your tree, loads it into the real game headless,
  and exercises machine setups against live game state.
