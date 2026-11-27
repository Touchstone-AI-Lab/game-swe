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

> **[#211]** My kitchen setup stopped working after updating. The furnace next to
> my mini-fridge just sits there with the ore and coal still inside the fridge,
> and nothing gets collected into it anymore either. My regular chests and stone
> chests out in the yard are fine — it's specifically the mini-fridge that
> machines ignore now.

> **[#213]** I develop an overlay mod that uses Automate's `GetMachineStates`
> API. Right after a save loads, the API returns nothing at all for locations
> that clearly contain machines — my overlay draws a blank farm even though the
> shipping bin and a shed full of kegs are right there. The moment the player
> sets up any chest next to any machine, everything pops into the overlay at
> once, including all the machines that were missing before.

> **[#216]** With some content mods installed, individual machines get stuck
> permanently: the machine shows as ready, but Automate never empties it, never
> feeds it new input, and the rest of the chain keeps working around it. Removing
> and re-placing the machine fixes it until it happens again. Emptying the stuck
> machine by hand in vanilla just discards a broken item and the machine carries
> on fine.

> **[#218]** The Junimo hut item options don't do what they say. I set seeds to
> Ignore because I keep mixed seeds in the hut for replanting, but Automate still
> moves them out into my chests. Weirdly, if I also set the fertilizer option to
> Ignore, the seeds stay put — but then my fertilizer piles up in the hut
> instead. The gem option works exactly as advertised.

> **[#221]** Ever since I built a second coop, the machines inside one of my
> coops are just dead — the chest sits there full of input and nothing happens.
> Which coop is the dead one seems random after loading. My first coop worked
> fine for two years before this, and machines everywhere else on the farm still
> work.

> **[#222]** Possibly related to the coop thing, possibly not: I have two big
> sheds full of preserves jars, and after the update only one shed's jars get
> refilled. If I demolish the second shed, the first one starts working again.
> Two different buildings of any one type seems cursed.

> **[#224]** I lost a whole season of chicks and I finally worked out why. I put
> an egg in the incubator in my coop, and by the next time I look the egg is
> sitting in the chest next to it instead — no chick, and the incubator is empty
> again. Same story in the barn with my ostrich egg. If I unhook the chest from
> the incubator the eggs hatch normally, so it's Automate doing it. Everything
> else — furnaces, kegs, preserves jars — fills and empties exactly when it
> should.

## Task

Diagnose and fix everything above. Behavior on the paths that already work must
not change.

## Notes

- The game is Stardew Valley 1.6.15 with SMAPI 4.1.10, installed at `/opt/stardew`.
- Build with `dotnet build Automate/Automate.csproj -p:GamePath=/opt/stardew -p:EnableModDeploy=false`.
- Do not modify anything under `/tests`.
- The grading harness compiles your tree, loads it into the real game headless,
  and exercises machine setups, the mod API, farm buildings (including several of
  the same type), and a Junimo hut against live game state.
