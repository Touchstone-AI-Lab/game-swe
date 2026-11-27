# Automate: machines wedge forever when a mod produces a broken output

You are working on **Automate**, a SMAPI mod for Stardew Valley that lets machines
pull input from and push output into adjacent chests automatically. The mod's
source is at `/app/StardewMods` (the mod project is `Automate/`; `Common/` is
shared code used by the same author's mods).

## Problem

Players running large modded setups report that individual machines sometimes get
stuck permanently: the machine shows as ready, but Automate never collects the
output, never feeds it new input, and the rest of the chain keeps running around
it. Removing and re-placing the machine fixes it until it happens again.

Digging through the reports, the common thread is other content mods with broken
machine rules that leave the machine holding an output item with a **stack size of
zero**. Emptying such a machine by hand in vanilla just discards the broken item
and the machine carries on. Under Automate the machine never recovers on its own.

## Task

Make Automate handle a machine holding a zero-size output stack the same way the
game handles emptying it manually: the broken output is discarded (a warning log
is fine), the machine leaves its ready state, and it continues processing further
input. Machines with normal output must keep behaving exactly as before.

## Notes

- The game is Stardew Valley 1.6.15 with SMAPI 4.1.10, installed at `/opt/stardew`.
- Build with `dotnet build Automate/Automate.csproj -p:GamePath=/opt/stardew`.
- Do not modify anything under `/tests`.
- The grading harness compiles your tree, loads it into the real game headless,
  and exercises machine chains against live game state, including the broken-mod
  scenario above.
