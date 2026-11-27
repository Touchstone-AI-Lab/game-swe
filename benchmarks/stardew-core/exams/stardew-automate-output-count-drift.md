# Automate: bar counts don't add up

You are working on **Automate**, a SMAPI mod for Stardew Valley that lets machines
pull input from and push output into adjacent chests automatically. The mod's
source is at `/app/StardewMods` (the mod project is `Automate/`; `Common/` is
shared code used by the same author's mods).

## Problem

Players on this build report that the number of items coming out of their
machines no longer matches what the machines made. Nobody has diagnosed it; these
are observations, not causes.

> **[#262]** My furnace chest makes copper bars out of thin air. I keep a stack of
> bars in that chest. Every time a batch finishes, the stack goes up by one *and* a
> single extra bar appears in an empty slot of the same chest.

> **[#263]** Same setup, but once the chest has no empty slot left (the bar stack
> itself still has plenty of room), the furnace never empties. It keeps showing a
> finished bar, and meanwhile the bar stack in the chest creeps up by one every few
> seconds.

> **[#265]** Different farm. My chest is completely full and the copper bar stack in
> it is already at 999. Finished bars simply disappear: the furnace resets and starts
> its next batch, but the new bar is not in the chest or anywhere else.

## Task

Fix Automate so that it never creates or destroys items. Every finished item must
end up exactly once either in a chest or still waiting in its machine, and a
finished item that joins a chest must go onto an existing stack of the same item
when that stack has room. Behavior on the paths that already work must not change.

## Notes

- The game is Stardew Valley 1.6.15 with SMAPI 4.1.10, installed at `/opt/stardew`.
- Build with `dotnet build Automate/Automate.csproj -p:GamePath=/opt/stardew -p:EnableModDeploy=false`.
- Do not modify anything under `/tests`.
- The grading harness compiles your tree, loads it into the real game headless, and
  checks machine setups against live game state.
