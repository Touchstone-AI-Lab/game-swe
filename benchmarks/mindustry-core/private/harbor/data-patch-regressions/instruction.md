# Harbor workspace

Complete this task in `/app/mindustry`; the verifier compiles its Java sources against the pinned Mindustry v159.7 dedicated server.

# Mindustry v159.7: dedicated server data patch regressions

## Context

`mindustry/` is the source tree of Mindustry (<https://github.com/Anuken/Mindustry>,
GPL-3.0, see `mindustry/LICENSE`) exactly as our dedicated servers run it: release
**v159.7** with the game core in `core/src`, the dedicated-server launcher and console
in `server/src`, and the annotation definitions in `annotations/src`. Game assets,
the Gradle build scripts and the upstream test suite are not part of the tree.

Our server build compiles every Java file under `core/src` and `server/src`, plus
`annotations/src/main/java/mindustry/annotations/Annotations.java`, with
`javac --release 17` against the official v159.7 `server-release.jar`, and runs the
dedicated server with the compiled classes ahead of that jar. Code generated at build
time (the `mindustry.gen` package, including the entity classes generated from the
component templates in `core/src/mindustry/entities/comp`) and every asset (maps,
bundles, sprites) come from the official jar and are not regenerated, so changes have
to be made in ordinary sources. Keep your changes inside `mindustry/core/src` and
`mindustry/server/src`.

## Server data assets

The dedicated server loads data assets from its `config/assets/` folder: data patches
from `config/assets/patches/` and custom content from `config/assets/content/<type>/`
(for example an item in `config/assets/content/items/rhenium-alloy.json`). It reads them
at start-up and whenever the `reloadassets` console command runs (which answers
`Loaded <n> data asset files.`), and applies them to every map it hosts afterwards.
Content defined this way is registered with the `dp-` prefix, so the item above is
`dp-rhenium-alloy` in game and in patches. After the files are removed and
`reloadassets` has run, hosting a map again undoes the patches. The active patches of the
running game are `state.data.getPatches()`; that list is also what the server sends to
joining players, whose clients apply it.

## Reports

Server operators report the following problems with server data assets.

- **Patches cannot use server-defined content.** With the item file above
  (`{"color": "ff00ff", "cost": 2}`) and the patch

  ```json
  {"name": "alloy-duo", "block": {"duo": {"requirements": ["dp-rhenium-alloy/7", "copper/5"]}}}
  ```

  in `config/assets/patches/`, hosting a map logs
  `Failed to read value duo.requirements ... No item found with name 'dp-rhenium-alloy'`
  and the duo keeps its vanilla requirements, although the item exists once the map runs.
- **Patched build towers keep building like vanilla ones.** The patch
  `{"name": "build-tower", "block": {"build-tower": {"buildSpeed": 3.5, "range": 300}}}`
  changes the block's `buildSpeed` and `range`, but the builder unit type the tower
  builds with (its `unitType`) keeps the vanilla build speed 1.5 and build range 200.
- **Patches for another planet are still handed out.** A patch with
  `"requiredPlanets": ["erekir"]` is correctly not applied on a Serpulo map such as
  `Ancient_Caldera`, but it is still listed among the active patches, so joining players
  apply it anyway.

## Expected behaviour

- Patches can refer to content defined in the server's content folder: the patch above
  applies without warnings and the duo then needs 7 `dp-rhenium-alloy` and 5 copper.
  Server-defined content keeps loading on its own (the item exists with its cost of 2).
- While a build-tower patch is active, the tower's builder unit uses the patched build
  speed and build range (3.5 and 300 above); hosting a map without the patch restores the
  vanilla values for both the block and its builder unit.
- Patches skipped because of `requiredPlanets` are not listed among the active patches;
  patches without a planet restriction, and patches restricted to the hosted map's
  planet, are applied and listed as before.
- Plain patches keep working: a patch that sets the duo's health to 777 applies while its
  map is hosted and is undone when a map is hosted without it.

## Evaluation

The verifier compiles your tree offline as described above and starts a real headless
v159.7 dedicated server with it, without network access. A trusted plugin inside that
server writes patch and content files into the server's `config/assets/` folder, runs
`reloadassets`, `host` and `stop`, and checks the resulting block and unit
properties, the server-defined content and the list of active patches.
