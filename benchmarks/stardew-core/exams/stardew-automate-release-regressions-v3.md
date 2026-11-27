# Automate: bug reports against this release branch

You are working on **Automate**, a SMAPI mod for Stardew Valley that lets machines
pull input from and push output into adjacent chests automatically. The mod's
source is at `/app/StardewMods` (the mod project is `Automate/`; `Common/` is
shared code used by the same author's mods).

## Problem

This branch missed a batch of fixes. Below is what users reported. Nobody has
diagnosed any of it — these are observations, not causes. They are not all the
same underlying issue, they are not one-report-per-issue either, and they are
spread across different parts of the mod.

> **[#241]** With some content mods installed, individual machines get stuck
> permanently: the machine shows as ready, but Automate never empties it, never
> feeds it new input, and the rest of the chain keeps working around it. Removing
> and re-placing the machine fixes it until it happens again. Emptying the stuck
> machine by hand in vanilla just discards a broken item and the machine carries
> on fine.

> **[#243]** I develop an overlay mod that uses Automate's `GetMachineStates`
> API. Right after a save loads, the API returns nothing at all for locations
> that clearly contain machines — my overlay draws a blank farm even though the
> shipping bin and a shed full of kegs are right there. The moment the player
> sets up any chest next to any machine, everything pops into the overlay at
> once, including all the machines that were missing before.

> **[#246]** I had a berry bush next to my kegs and everything was fine until I
> chopped the bush down. After that the whole setup in that corner went quiet —
> the kegs still had fruit in the chest and just stopped. My log has a wall of
> errors from Automate. Replacing the chest fixed it.

> **[#248]** Ever since I built a second coop, the machines inside one of my
> coops are just dead — the chest sits there full of input and nothing happens.
> Which coop is the dead one seems random after loading. My first coop worked
> fine for two years before this, and machines everywhere else on the farm still
> work.

> **[#249]** Possibly related to the coop thing, possibly not: I have two big
> sheds full of preserves jars, and after the update only one shed's jars get
> refilled. If I demolish the second shed, the first one starts working again.
> Two different buildings of any one type seems cursed.

## Task

Diagnose and fix everything above. Behavior on the paths that already work must
not change.

## Notes

- The game is Stardew Valley 1.6.15 with SMAPI 4.1.10, installed at `/opt/stardew`.
- Build with `dotnet build Automate/Automate.csproj -p:GamePath=/opt/stardew -p:EnableModDeploy=false`.
- Do not modify anything under `/tests`.
- The grading harness compiles your tree, loads it into the real game headless,
  and exercises machine setups, the mod API, farm buildings (including several of
  the same type), and terrain features against live game state.
