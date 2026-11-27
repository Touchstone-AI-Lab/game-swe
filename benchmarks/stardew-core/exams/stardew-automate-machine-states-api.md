# Automate: GetMachineStates API misses locations with only non-automated machines

You are working on **Automate**, a SMAPI mod for Stardew Valley that lets machines
pull input from and push output into adjacent chests automatically. The mod's
source is at `/app/StardewMods` (the mod project is `Automate/`; `Common/` is
shared code used by the same author's mods).

## Problem

Automate exposes a mod API (see `IAutomateAPI`) with a `GetMachineStates` method
that reports per-tile machine states in a location. Overlay mods like Data Layers
use it to render which machines are automated, processing, done, or not connected
to any chest.

A mod developer reports: "`GetMachineStates` returns an empty dictionary for a
location where the only machines are ones Automate isn't automating — for example
a shed with machines but no chest connected to them. Those are exactly the
machines my overlay needs to flag for the player. If the location also contains at
least one working machine group, the non-automated ones show up fine alongside it.
The machines appear correctly as soon as I connect a chest, so Automate clearly
knows about them."

## Task

Make `GetMachineStates` report machine states for locations whose machines are all
non-automated, matching how those machines are already reported when an automated
group exists in the same location. Behavior for locations with automated machine
groups must not change.

## Notes

- The game is Stardew Valley 1.6.15 with SMAPI 4.1.10, installed at `/opt/stardew`.
- Build with `dotnet build Automate/Automate.csproj -p:GamePath=/opt/stardew`.
- Do not modify anything under `/tests`.
- The grading harness compiles your tree, loads it into the real game headless,
  and exercises the mod API against live game state.
