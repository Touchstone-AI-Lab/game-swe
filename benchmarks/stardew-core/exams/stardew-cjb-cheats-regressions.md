# CJB Cheats Menu: bug reports against this release

You are working on **CJB Cheats Menu**, a SMAPI mod for Stardew Valley that adds an
in-game menu of cheats. Cheats can also be switched on by editing the mod's
`config.json`, and the enabled ones keep running on their own while you play. The
mod's source is at `/app/StardewMods` (the mod project is `CJBCheatsMenu/`;
`Common/` is shared code used by the same authors' mods).

## Problem

Players filed the reports below against this release. They are observations, not
diagnoses, and they do not necessarily map one-to-one onto causes in the code.

> **One Hit Kill and grubs.** With One Hit Kill on, every grub I meet in the mines
> starts wriggling and turns into a cave fly a few seconds later, before I've even
> touched it. Without the cheat a grub only does that once it's badly hurt. Other
> monsters behave normally with the cheat on: they just die in one hit. Please don't
> "fix" this by changing every monster's maximum health; my vampiric weapon heals me
> based on the maximum health of what I kill, and that must stay as it is.

> **Auto-Feed Animals with an empty silo.** Auto-Feed Animals only fills my coop's
> troughs while there is hay in a silo. Once the silos run dry, the troughs stay
> empty and my chickens go hungry. This is a cheat; when there's no hay left it
> should still fill the troughs. When the silos do have hay it should keep taking the
> hay from them as it does now.

> **Auto-Pet Animals outside the farm.** I use a mod that places a friendly goat in
> Pelican Town as decoration. With Auto-Pet Animals on, the cheat keeps petting that
> goat. Auto-Pet Animals should only pet animals in places where I can put farm
> buildings (like my farm), including the animals living inside those buildings.

> **Auto-Pet Pets outside the farm.** Similar thing with pets: a mod adds a dog NPC
> in town that says something every time it's petted, and Auto-Pet Pets pets it
> constantly, so its line repeats all day. Auto-Pet Pets should only pet the pets
> that live at home, on the farm or inside the farmhouse or a cabin.

> **Always Treasure and golden chests.** Since I got the fishing mastery I sometimes
> find golden treasure chests while fishing. With Always Treasure on, every catch has
> a chest, but none of them is ever golden. The golden ones should still show up at
> the game's usual rate for someone with the fishing mastery (and never for someone
> without it).

## Task

Diagnose and fix everything reported above. Behavior that already works must not
change: One Hit Kill still takes monsters to a single hit without lowering their
maximum health, Auto-Feed Animals still uses silo hay when there is some, farm
animals and pets at home are still petted, and Always Treasure still gives every
catch a chest.

## Notes

- The game is Stardew Valley 1.6.15 with SMAPI 4.1.10, installed at `/opt/stardew`.
- Build with `dotnet build CJBCheatsMenu/CJBCheatsMenu.csproj -p:GamePath=/opt/stardew`.
- Do not modify anything under `/tests`.
- The grading harness compiles your tree, loads it into the real game headless with
  these cheats switched on in `config.json`, and checks live game state.
