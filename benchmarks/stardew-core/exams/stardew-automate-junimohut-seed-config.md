# Automate: Junimo hut seed setting doesn't do what it says

You are working on **Automate**, a SMAPI mod for Stardew Valley that lets machines
pull input from and push output into adjacent chests automatically. The mod's
source is at `/app/StardewMods` (the mod project is `Automate/`; `Common/` is
shared code used by the same author's mods).

## Problem

Automate can treat Junimo huts as machines: things Junimos collect into the hut get
moved into connected chests. Players can configure this per item type — there are
separate config options for what to do with gems, fertilizer, and seeds found in
the hut (ignore them, or move them into chests).

Players report the **seeds** option is broken. One writes: "I set seeds to Ignore
because I keep mixed seeds in the hut for replanting, but Automate still moves them
out into my chests. Weirdly, if I also set the fertilizer option to Ignore, the
seeds stay put — but then my fertilizer piles up in the hut instead. The gem
option works exactly as advertised."

## Task

Make the Junimo hut seed behavior follow its own config option, without changing
how the other item types are handled.

## Notes

- The game is Stardew Valley 1.6.15 with SMAPI 4.1.10, installed at `/opt/stardew`.
- Build with `dotnet build Automate/Automate.csproj -p:GamePath=/opt/stardew`.
- Do not modify anything under `/tests`.
- The grading harness compiles your tree, loads it into the real game headless,
  and exercises a Junimo hut against live game state with a specific config.
