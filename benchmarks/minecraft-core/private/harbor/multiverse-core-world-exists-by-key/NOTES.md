# Maintenance notes: multiverse-core-world-exists-by-key

## Upstream

- Repository: https://github.com/Multiverse/Multiverse-Core (BSD-3-Clause,
  `LICENSE.md` kept in the starter).
- Base commit: `54900f55a94cf8e6dad22c2d9f2db8ed01d3713e` (merge of PR #3469,
  parent of the fix).
- Fix: merge commit `5f43d756e596c73e8fd57b4f89109418851f95c9` of PR #3470
  "Fix world exist checking not looking up both name and key" (head
  `142ef02c`, merged 2026-05-08, shipped in Multiverse-Core 5.7.0). The PR has
  no linked issue and changes no test.
- The starter is `git archive` of the base commit without `.github/`, `docs/`
  and `config/` (Doxygen file, release images, a locale script and a
  checkstyle xml that `build.gradle`/`settings.gradle` never reference).

## Defect

Since 5.7 a world is identified by a `WorldKeyOrName`: a `Name` variant
carries the Bukkit name plus a derived usable key (`the_end` ->
`minecraft:the_end`, `foo` -> `minecraft:foo`), a `Key` variant carries the
namespaced key plus a derived usable name (`gcb:keyed` -> `gcb_keyed`,
`minecraft:the_end` -> `world_the_end`). `WorldStore` registers every world
under both its key string and its legacy (Bukkit) name, and Paper names a
world created with `WorldCreator.ofKey(gcb:keyed)` `keyed`, not `gcb_keyed`.

`WorldManager.parseCreateWorldOptionsKeyOrName`, `importWorld` and
`parseCloneWorldOptionsNewWorld` decide `WORLD_EXIST_LOADED` /
`WORLD_EXIST_UNLOADED` with `getLoadedWorld(keyOrName.usableName())` and
`getWorld(keyOrName.usableName())` only. Whenever the usable name is not the
string the world is registered under, the check misses:

- `createWorld(worldName("the_end"))` while `world_the_end` is loaded: the
  usable name `the_end` is neither `world_the_end` nor `minecraft:the_end`;
  Paper then throws `IllegalArgumentException` ("Cannot create a world with
  key minecraft:the_end and name the_end one (or both) already match a world
  that exists") and the result is `WORLD_CREATOR_FAILED`.
- `createWorld(worldKey(gcb:keyed))` twice: the usable name `gcb_keyed` is
  not the registered name `keyed`; Paper returns the existing world (name and
  key both match it) and `WorldsConfigManager.addWorldConfig` throws
  `IllegalStateException: WorldConfig for world gcb:keyed already exists`.
  After an unload the same call re-loads the world folder through Paper and
  then throws the same exception. `cloneWorld(fromTo(world, gcb:keyed))`
  copies the source folder to `gcb_keyed` first and ends the same way.
- `importWorld` additionally locates an already-loaded Bukkit world with
  `Bukkit.getWorld(keyOrName.usableName())` only, so `importWorld(worldKey(
  gcb:direct))` for a loaded Bukkit world `direct` falls through to the folder
  check (`gcb_direct` does not exist) and fails with `WORLD_FOLDER_INVALID`.

## Reference fix

`solution/after/` carries the upstream main-source change only:

- `WorldStore` gains `getWorld`/`isWorld`/`getLoadedWorld`/`isLoadedWorld`/
  `getUnloadedWorld`/`isUnloadedWorld`/`getUnloadedWorldRef` overloads for
  `NamespacedKey` and `WorldKeyOrName`; the `WorldKeyOrName` overloads look up
  the usable key first and fall back to the usable name.
- `WorldManager` switches the six existence `failIf` checks to
  `worldStore::isLoadedWorld` / `isUnloadedWorld` / `isWorld` with the
  `WorldKeyOrName` argument, and `importWorld` locates the loaded Bukkit world
  through the new `BukkitCompatibility.getWorldByNameOrKey(WorldKeyOrName)`
  (name first, then the reflective `Bukkit.getWorld(NamespacedKey)`).
- `WorldKeyOrName` swaps jspecify annotations for jetbrains ones and
  implements `LocalizableMessage`; this is cosmetic for the task.

All 177 base tests pass with and without the fix (checked by the oracle gate).

## Build

Gradle 8.10.2 wrapper, convention plugin `org.mvplugins.multiverse-plugin`
1.2.2, `serverApiVersion = '1.21.11-R0.1-SNAPSHOT'` (resolved
`io.papermc.paper:paper-api:1.21.11-R0.1-SNAPSHOT`), tests in Kotlin with
MockBukkit 4.110.0. The convention plugin disables the plain `jar` task, so the
artifact is `shadowJar` -> `build/libs/multiverse-core-local.jar`. Gradle
resolves the JUnit platform launcher only while running tests, so the image
warm-up runs `test` online once before the offline proof.

## Why the repository matters

The solver has to understand the two-identity model (`WorldKeyOrName.Name` vs
`Key`, `usableName()` vs `usableKey()`), how `WorldStore` registers worlds
(key string and legacy name, case-insensitive), how Paper maps names to keys
and keys to names, and that the same existence decision is made at three call
sites plus the separate Bukkit lookup inside `importWorld`. A fix that
consults only the key (dropping the name lookup) breaks name-based rejection
for custom-key worlds; a fix that repairs only the create/clone sites leaves
the import-by-key path broken.

## Live-server design

All server cases use the public `WorldManager` API through
`MultiverseCoreApi`, flat worlds, no spawn adjustment and no player. The
verifier server runs with `level-name=world`, `allow-nether=false` and
`allow-end: true`, so `world_the_end` (key `minecraft:the_end`) is the loaded
default dimension that Multiverse auto-imports at startup.

- `plugin is enabled` (sentinel).
- `worlds resolve by name and by key string` (preserved): a world created by
  name resolves through `getWorld`/`getLoadedWorld`/`isWorld`/`isLoadedWorld`
  with both `gcb_lookup` and `minecraft:gcb_lookup`; the End resolves with
  `world_the_end` and `minecraft:the_end`.
- `creating or cloning under an existing name is rejected` (preserved):
  `gcb_plain` (by name) and `gcb:named` (by key, Bukkit name `named`) exist;
  `createWorld(worldName("gcb_plain"))`, `createWorld(worldName("named"))`
  and `cloneWorld(fromTo(gcb_plain, "named"))` fail with
  `WORLD_EXIST_LOADED`; after unloading `gcb_plain` the create fails with
  `WORLD_EXIST_UNLOADED`. Passes on the starter because the usable name of a
  `Name` request is the registered name. A key-only fix breaks it.
- `create is rejected when the name is an existing world key` (target):
  `createWorld(worldName("the_end"))` must fail with `WORLD_EXIST_LOADED`, no
  `the_end` Bukkit world or folder appears and `getWorlds()` is unchanged.
  Starter: `WORLD_CREATOR_FAILED`.
- `create is rejected when the key belongs to an existing world` (target):
  `gcb:keyed` created by key; creating it again must fail with
  `WORLD_EXIST_LOADED`; after `unloadWorld` it must fail with
  `WORLD_EXIST_UNLOADED` and the Bukkit world `keyed` stays unloaded.
  Starter: the first create throws `IllegalStateException`.
- `clone is rejected when the target key belongs to an existing world`
  (target): `cloneWorld(fromTo(gcb_clone_source, gcb:clone_target))` must fail
  with `WORLD_EXIST_LOADED` and no `gcb_clone_target` folder may appear.
  Starter: the folder is copied and the import step throws.
- `import adopts a loaded Bukkit world addressed by key` (target): the grader
  creates the Bukkit world `gcb:direct` with `WorldCreator.ofKey` (Paper API);
  `importWorld(ImportWorldOptions.worldKey(gcb:direct))` must succeed and
  adopt that world instance with key `gcb:direct` and name `direct`. Starter:
  `WORLD_FOLDER_INVALID`.

Every case throws through a `call(...)` helper that turns an unexpected
exception into an assertion message naming the exception, so the starter's
`IllegalStateException` shows up as the case failure rather than a bare stack
trace.

## 0.2.0 changes

The exam no longer says which check is wrong or that it "looks at only one of the
two identities", and no longer quotes Paper's exception texts; it describes the
`/mv` symptoms and states the existence contract. Three target cases complete the
coverage of the upstream change, which switched the existence checks of all three
operations (create, import, clone) to both identities:

- `import is rejected when the key belongs to an existing world`: `gcb:imported_twice`
  created by key; `importWorld(worldKey(...))` must fail with `WORLD_EXIST_LOADED`,
  and after `unloadWorld` with `WORLD_EXIST_UNLOADED` without loading the world
  again. Starter: `WORLD_FOLDER_INVALID` (the folder `gcb_imported_twice` derived
  from the usable name does not exist).
- `import is rejected when the name is an existing world key`:
  `importWorld(worldName("the_end"))` must fail with `WORLD_EXIST_LOADED`.
  Starter: `WORLD_FOLDER_INVALID`.
- `clone is rejected when the target name is an existing world key`:
  `cloneWorld(fromTo(gcb_clone_end, "the_end"))` must fail with
  `WORLD_EXIST_LOADED`, copy no `the_end` folder and create no Bukkit world.
  Starter: the folder is copied and the import step fails.

A repair that fixes the create path alone now fails four target cases; one that
consults only the key still fails the preserved name-based case; one that fixes
the existence checks but not the Bukkit lookup inside `importWorld` fails only
`import adopts a loaded Bukkit world addressed by key`.

## Merge review (0.2.0)

Considered and left out: PR #3479 ("fix/key-bugs", regen and clone crashes for keyed worlds) is in the same family but five merges later, with the jspecify refactor #3471 and two features in between, and its behaviour depends on the 26.x dimension storage that Paper 1.21.11 does not use. The task keeps PR #3470 alone and grows by covering the import and clone paths of the same existence check.
