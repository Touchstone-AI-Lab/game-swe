# Multiverse-Core: worlds with upper-case letters in their name break on unload, remove, delete and regen

## Context

`plugin/` is the Multiverse-Core Paper plugin (BSD-3-Clause) at an upstream
commit. It manages additional worlds for a Paper 1.21 server. The `/mv`
commands and other plugins drive it through the `WorldManager` service
(`MultiverseCoreApi.get().getWorldManager()`): `createWorld`, `loadWorld`,
`unloadWorld`, `removeWorld`, `deleteWorld` and `regenWorld` with their
`...WorldOptions` builders, and the lookups `getWorld`, `getLoadedWorld`,
`getUnloadedWorld`, `isWorld`, `isLoadedWorld`, `getWorlds` and
`getUnloadedWorlds`.

Multiverse world names are case-insensitive: every lookup finds a world under
any casing of its name (`getWorld("world2")`, `getWorld("World2")` and
`getWorld("WORLD2")` resolve the same world). A world nevertheless keeps the
exact name it was created with: `MultiverseWorld.getName()`, the Bukkit world,
the world folder and the world's entry in `plugins/Multiverse-Core/worlds.yml`
all use that original spelling.

## Symptom

Server owners report that worlds whose names contain an upper-case letter can be
created, listed and looked up, but cannot be managed afterwards:

```text
/mv create World2 normal      -> created
/mv unload World2             -> fails with an internal error
```

After that failed unload the server itself no longer has `World2` loaded, yet
Multiverse still reports it as a loaded world. `/mv remove`, `/mv delete` and
`/mv regen` on such a world either fail the same way or report success while the
world stays known to Multiverse. The same commands work for worlds whose names
are entirely lower-case. Plugins that call the `WorldManager` methods listed
above see the same failures.

## Task

Repair the plugin so that a world whose name contains upper-case letters goes
through its whole lifecycle exactly like a lower-case one. For such a world
`<Name>`:

- `unloadWorld(UnloadWorldOptions.world(...))` succeeds and the Bukkit world is
  unloaded. Afterwards the world is not loaded under any casing of its name
  (`isLoadedWorld` is false, `getLoadedWorld` is empty), it is tracked as an
  unloaded world (`getUnloadedWorld("<Name>")` returns it, with `getName()`
  still `<Name>`), it is still known (`isWorld` is true) and `getWorlds()`
  lists it exactly once.
- An unloaded world can be loaded again with `loadWorld(LoadWorldOptions.world(...))`.
  Afterwards it is loaded, `getUnloadedWorld` no longer returns it under any
  casing, its Bukkit world is loaded, it keeps its original name and
  `getWorlds()` lists it exactly once.
- `removeWorld(RemoveWorldOptions.world(...))` succeeds whether the world is
  loaded or unloaded, and the world is forgotten completely: under every casing
  `isWorld` is false and `getWorld`, `getLoadedWorld` and `getUnloadedWorld`
  are empty, `getWorlds()` and `getUnloadedWorlds()` no longer list it, and
  `worlds.yml` holds no entry for it. A removed loaded world's Bukkit world is
  unloaded; removing keeps the world folder.
- `deleteWorld(DeleteWorldOptions.world(...))` succeeds, forgets the world in
  the same way and deletes its folder.
- `regenWorld(RegenWorldOptions.world(...).seed(<seed>))` succeeds. Afterwards
  exactly one world with that name is known; it is loaded (also in Bukkit),
  keeps its original name, has the new seed and still has its `worlds.yml`
  entry.

The rest of the behaviour must not change:

- Lookups stay case-insensitive (`isWorld`, `isLoadedWorld`, `getWorld` and
  `getLoadedWorld` find a world under any casing; an unknown name finds
  nothing), and a world is listed once.
- A created world keeps its original name everywhere: `getName()`, the Bukkit
  world's name, the folder name and the `worlds.yml` entry are spelled as it
  was created, even when it is looked up with another casing.
- Lower-case worlds keep working exactly as before: unload, load again, remove
  (folder kept) and delete (folder deleted).

Keep the change inside `plugin/src/main/java`. The build files, the Gradle
wrapper and the existing tests under `plugin/src/test` are frozen: the verifier
restores them from the starter before building, and every existing upstream test
must keep passing.

## Evaluation

The verifier builds the plugin offline with the repository's Gradle wrapper
(`shadowJar`), runs the upstream MockBukkit test suite, and then loads the built
jar into a real Paper 1.21.11 dedicated server without players. There it creates
flat worlds with lower-case and mixed-case names and unloads, loads, removes,
deletes and regenerates them through the `WorldManager` API, checking the
lookups above under several casings, the Bukkit worlds, the world folders and
`plugins/Multiverse-Core/worlds.yml`.
