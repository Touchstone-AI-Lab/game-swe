# Automate: something is emptying my incubators

You are working on **Automate**, a SMAPI mod for Stardew Valley that lets machines
pull input from and push output into adjacent chests automatically. The mod's
source is at `/app/StardewMods` (the mod project is `Automate/`; `Common/` is
shared code used by the same author's mods).

## Problem

> **[#233]** I lost a whole season of chicks and I finally worked out why. I put
> an egg in the incubator in my coop, and by the next time I look the egg is
> sitting in the chest next to it instead — no chick, and the incubator is empty
> and ready for another egg I don't have. It's not the animals eating it or
> anything; the egg is right there in the chest. Same story in the barn with my
> ostrich egg. If I unhook the chest from the incubator the eggs hatch normally,
> so it's Automate doing it.
>
> Everything else on my farm is fine — furnaces, kegs, preserves jars, my casks
> full of wine — those all fill up and get emptied exactly when they should. It's
> just the incubators.

## Task

Stop Automate from emptying a machine that is still working on what it was given,
while leaving collection from machines that have genuinely finished unchanged.

## Notes

- The game is Stardew Valley 1.6.15 with SMAPI 4.1.10, installed at `/opt/stardew`.
- Build with `dotnet build Automate/Automate.csproj -p:GamePath=/opt/stardew -p:EnableModDeploy=false`.
- Do not modify anything under `/tests`.
- The grading harness compiles your tree, loads it into the real game headless,
  and exercises machines across several in-game hours, inside farm buildings as
  well as outdoors.
