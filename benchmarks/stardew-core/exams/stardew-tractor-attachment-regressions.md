# Tractor Mod: bug reports against this release

You are working on **Tractor Mod**, a SMAPI mod for Stardew Valley that adds a
tractor you build at Robin's and ride around the farm. While you ride it, the tool or
item you hold is applied automatically to every tile within a configurable distance
around the tractor, according to per-tool options in the mod's `config.json` (the
same options appear in its config UI; `TractorMod/i18n/default.json` has their
names and descriptions). The mod's source is at `/app/StardewMods` (the mod project
is `TractorMod/`; `Common/` is shared code used by the same author's mods).

## Problem

Players filed the reports below against this release. They are observations, not
diagnoses, and they do not necessarily map one-to-one onto causes in the code.

> **Axe and grown fruit trees.** I turned on "Chop Fruit Trees (Saplings)" to clear
> young fruit trees and left "Chop Fruit Trees (Grown)" off. Driving past my orchard
> with the axe, the tractor chopped down my fully grown cherry trees too. Saplings
> should be cleared; grown fruit trees should be left alone unless the grown-trees
> option is on.

> **Seeds and garden pots.** I keep tea bushes in garden pots. When I drive by with
> parsnip seeds, the tractor sows seeds into the pots that already hold a bush, and
> the pot ends up with a crop planted under the bush. Empty garden pots and ordinary
> tilled soil should still be sown.

> **Custom attachments.** I listed `Parsnip` and `Torch` under
> `CustomAttachments` so I could use them from the tractor. Torches get placed around
> the tractor as expected. But when I hold parsnips, the tractor drops them on the
> ground as if they were placeable objects, one per tile, until my stack is gone.
> Items the game doesn't let you place by hand shouldn't be placed by the tractor
> either.

> **Pickaxe and stones.** I switched "Break Mine Stones" off because I want to keep
> the stones on my farm, and switched on "Break Objects" ("whether to break placed
> objects") so the tractor clears old torches and similar things. Now the tractor smashes every stone
> it drives past anyway. Stones aren't placed objects; they should only be broken
> when "Break Mine Stones" is on. Placed objects like torches should still be broken.

## Task

Diagnose and fix everything reported above. Behavior that already works must not
change: saplings are cleared when that option is on, empty garden pots are sown,
placeable custom attachments are placed, and placed objects are broken when that
option is on.

## Notes

- The game is Stardew Valley 1.6.15 with SMAPI 4.1.10, installed at `/opt/stardew`.
- Build with `dotnet build TractorMod/TractorMod.csproj -p:GamePath=/opt/stardew`.
- Do not modify anything under `/tests`.
- The grading harness compiles your tree, loads it into the real game headless with
  a fixed `config.json`, rides a tractor on the farm, and checks live game state.
