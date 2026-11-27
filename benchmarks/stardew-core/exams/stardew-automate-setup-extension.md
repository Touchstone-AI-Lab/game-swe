# Automate: extended setups stay idle until a reload

You are working on **Automate**, a SMAPI mod for Stardew Valley that lets machines
pull input from and push output into adjacent chests automatically. The mod's
source is at `/app/StardewMods` (the mod project is `Automate/`; `Common/` is
shared code used by the same author's mods).

## Problem

Players on this build report that growing an existing setup sometimes has no
effect until they save and reload. Nobody has diagnosed it; these are
observations, not causes.

> **[#273]** I had a working smelting row: a chest with copper ore and coal, and a
> furnace on the chest's right. I placed a second furnace on the chest's left side.
> It never takes any ore. After I save, quit and reload, it works. If I place the new
> furnace next to the first furnace instead, it starts right away.

> **[#276]** Somewhere else on the farm my chest had run empty, so its furnace sat
> idle. I placed a new chest with copper ore and coal right next to the empty chest,
> on the side away from the furnace. The furnace ignores the new chest until I reload
> the save.

## Task

Fix Automate so that adding a machine or chest that connects to an existing setup
takes effect immediately, without reloading the save. Behavior on the paths that
already work must not change.

## Notes

- The game is Stardew Valley 1.6.15 with SMAPI 4.1.10, installed at `/opt/stardew`.
- Build with `dotnet build Automate/Automate.csproj -p:GamePath=/opt/stardew -p:EnableModDeploy=false`.
- Do not modify anything under `/tests`.
- The grading harness compiles your tree, loads it into the real game headless, and
  checks machine setups against live game state.
