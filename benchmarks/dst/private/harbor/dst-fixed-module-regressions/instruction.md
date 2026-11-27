# Harbor workspace

The mod to repair is the source tree in `/app/mod`; the verifier grades that directory.

# DST Fixed: six optional modules misbehave on our server

## Context

`/app/mod` is **DST Fixed** (Chinese name 纯净辅助, Apache-2.0), a Don't Starve
Together server mod by Ducklantis, at a recent upstream release. It is a
collection of small optional modules. Each module has a configuration option in
`modinfo.lua`, and `modmain.lua` loads the modules whose option is enabled.

Our dedicated server has these six modules switched on. Every other option is
at its default.

| Option | Module (as labelled in the configuration screen) |
| --- | --- |
| `NAMEABLE_WATCHES` | Nameable Backtrek Watch |
| `EQUIPMENT` | Combinable Equipment |
| `SANDSTONE` | Enhanced Sand Stone |
| `BLOCKABLEPOOPING` | Block Pooping With a Bung |
| `GLOMMER` | Glommer Statue Repairing |
| `GATHERMOONGLASS` | Gather Moon Dial's Glass |

## Reports from the server

> **Watches.** The option is on, but a Feather Pencil does nothing to a
> Backtrek Watch or a Rift Watch. There is no way to give a watch a name.
> **Combining gear.** Durability combining works: two spears become one spear
> with their uses added together. But when we combine two Turf-Raiser Helms,
> the turf that was loaded in the helm used up as material is simply gone.

> **Desert Stone.** A Desert Stone used from the inventory opens a temporary
> Lazy Deserter, and our other Lazy Deserters link to it as expected. When the
> player stops channeling, though, the server logs a Lua error, and the other
> Lazy Deserters keep pointing at the temporary one.

> **Bungs.** Once a single koalefant has been plugged with a bung, every
> koalefant killed afterwards drops a bung too, sometimes more than one. The
> plugged one also keeps its bung and stays plugged after a restart, as it
> should.

> **Glommer's statue.** We switched Glommer Statue Repairing on for a world we
> had already been playing for a while. Players had mined part of the Glommer
> statue there before, and that statue refuses Marble. Statues mined after the
> option was on take Marble as they should.

> **Moon dials.** When a moon storm ends, the Celestial Portal receives one
> more piece of Moon Glass than there were glassed moon dials.

## Expected behaviour

- **Nameable Backtrek Watch.** A Feather Pencil can be used on a Backtrek Watch
  (`pocketwatch_recall`) or a Rift Watch (`pocketwatch_portal`), and this opens
  the watch for writing. Once the player submits a text, the watch's display
  name becomes `<watch name> (<text>)`. The name survives saving and loading
  the watch. Starting to name a watch uses up one Feather Pencil; the rest of
  a stack stays in the player's inventory.
- **Combinable Equipment.** Combining two items of the same kind still adds the
  consumed item's durability to the kept one, capped at full, and still uses up
  the consumed item. Anything stored inside the consumed item (the turf in a
  Turf-Raiser Helm, for example) is dropped where that item was. It is never
  deleted.
- **Enhanced Sand Stone.** Using a Desert Stone from the inventory still opens a
  temporary Lazy Deserter that the player channels, and other Lazy Deserters
  link to it. When the channeling stops, no error is raised, and every Lazy
  Deserter that was linked to the temporary one is released. That is what the
  base game does when a Lazy Deserter stops channeling.
- **Block Pooping With a Bung.** A beefalo, baby beefalo or koalefant accepts
  one bung (`trinket_8`), refuses a second one, and stays blocked after a save
  and reload. When a blocked creature dies it drops exactly one bung in
  addition to its normal loot. A creature that was never given a bung never
  drops one, whatever happened to other creatures of its kind.
- **Glommer Statue Repairing.** A Glommer statue (`statueglommer`) that has
  been partly mined can be repaired with Marble. Each Marble restores two
  points of work, up to the work of a full statue (`TUNING.ROCKS_MINE`), and a
  full statue takes no more Marble. This holds for every statue in the world,
  including one loaded from a save the base game wrote before the option was
  switched on.
- **Gather Moon Dial's Glass.** When a moon storm ends while the glassed moon
  dials are unattended and a Celestial Portal exists, the portal receives
  exactly one piece of Moon Glass per glassed dial. With no Celestial Portal,
  each dial drops its own single piece beside itself, as before.

## Evaluation

The verifier runs the mod on a real Don't Starve Together dedicated server
(Steam app 343050, build 24700372), offline, with the configuration above. A
Wilson spawned on the server stands in for the player. The verifier drives the
game's own actions: renaming with a Feather Pencil, combining, using a Desert
Stone, and repairing with Marble. It trades bungs through the creatures'
`trader` component and generates their death loot through `lootdropper`. It
mines Glommer statues through their `workable` component, and it loads one
statue from the save data the base game writes for a partly mined statue. It
starts and ends moon storms with the world's storm event, and it saves and
reloads entities through their save records. Some checks run a moment later
on the world clock. It then inspects display names, durability, the work left
in the statues, the items left in the world and in the player's inventory, and
where each Lazy Deserter's teleporter leads.
