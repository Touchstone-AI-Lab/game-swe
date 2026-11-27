# Automate: my whole farm stopped after installing another mod

You are working on **Automate**, a SMAPI mod for Stardew Valley that lets machines
pull input from and push output into adjacent chests automatically. The mod's
source is at `/app/StardewMods` (the mod project is `Automate/`; `Common/` is
shared code used by the same author's mods).

## Problem

> **[#251]** I installed another mod this week and now Automate does nothing at
> all on my farm. Not "some machines" — nothing. Furnaces, preserves jars, the
> lot, all sitting there full with chests full of input right next to them. They
> worked fine the day before.
>
> The other mod's author says their mod is fine on its own, and honestly it does
> seem to work — the feature it advertises is there. My SMAPI log has errors in
> it that mention that mod by name, over and over, once per scan by the look of
> it. If I uninstall it, Automate goes back to normal immediately.
>
> I don't think one broken mod should be able to take out everything Automate
> does across an entire farm. Even if the other mod is at fault, Automate is the
> one that stops working.

Other mods are installed alongside Automate in this environment, in
`/opt/stardew/Mods`.

## Task

Make Automate resilient here: a failure originating in another mod must not stop
Automate from automating the rest of a location. Machines that are unaffected
must keep working, and Automate should say what went wrong rather than failing
silently. Behavior with no misbehaving mod present must not change.

## Notes

- The game is Stardew Valley 1.6.15 with SMAPI 4.1.10, installed at `/opt/stardew`.
- Build with `dotnet build Automate/Automate.csproj -p:GamePath=/opt/stardew -p:EnableModDeploy=false`.
- Do not modify anything under `/tests`, and do not modify or remove other mods in
  `/opt/stardew/Mods` — the fix must be in Automate.
- The grading harness compiles your tree, loads it into the real game headless
  with the same set of mods installed, and exercises machines against live game
  state.
