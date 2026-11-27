# Harbor workspace

Complete this task in `/app/plugin`; the repository's build files, dependency declarations and upstream tests are frozen and restored by the verifier.

# Multiverse-Core: creating, importing or cloning a world does not notice that the world already exists

## Context

`plugin/` is the Multiverse-Core Paper plugin (BSD-3-Clause) at an upstream
commit. It manages additional worlds for a Paper 1.21 server through the
`WorldManager` service, which other plugins reach through
`MultiverseCoreApi.get().getWorldManager()` and which drives `/mv create`,
`/mv import`, `/mv clone` and the other `/mv` commands.

Every Multiverse world carries two identities: its Bukkit name
(`MultiverseWorld.getName()`) and its namespaced key
(`MultiverseWorld.getKey()`, for example `minecraft:the_end`). The lookups
`getWorld`, `getLoadedWorld`, `getUnloadedWorld`, `isWorld` and
`isLoadedWorld` accept either the name or the key string:
`getWorld("world_the_end")` and `getWorld("minecraft:the_end")` resolve the
same End dimension. Creating, importing and cloning accept either identity as
well (`CreateWorldOptions.worldName(...)` / `worldKey(...)`,
`ImportWorldOptions.worldName(...)` / `worldKey(...)`,
`CloneWorldOptions.fromTo(world, name)` / `fromTo(world, key)`); a string
containing `:` is parsed as a key, otherwise as a name. Paper derives the key of
a world created by name (`the_end` becomes `minecraft:the_end`, any other name
becomes `minecraft:<lower-cased name>`) and names a world created from a key
after the key's path (`gcb:keyed` is the Bukkit world `keyed`). A request
therefore also has two identities: the name it gives or implies and the key it
gives or implies.

Before creating, importing or cloning, Multiverse refuses a request whose world
already exists: the attempt fails with `WORLD_EXIST_LOADED` (or
`WORLD_EXIST_UNLOADED` for an unloaded world) of the operation's failure-reason
enum, without touching any world or folder.

## Symptom

On a real server whose End dimension `world_the_end` (key `minecraft:the_end`)
is loaded, server owners and plugin authors report:

- `/mv create the_end normal` is not refused as an existing world; it ends in the
  generic "Failed!" with an exception from Paper in the console.
- `/mv create gcb:keyed normal` run twice: the second run is not refused but ends
  in an exception, and after `/mv unload gcb:keyed` the same command loads the
  world again instead of being refused. `/mv clone <world> gcb:keyed` behaves the
  same way and copies the world folder before it fails, and so does
  `/mv clone <world> the_end`.
- `/mv import gcb:keyed normal` for that existing Multiverse world is not refused
  either: it complains that the folder is not a valid world. The same happens for
  `/mv import the_end normal`.
- `/mv import gcb:direct normal`, for a world that another plugin has already
  loaded under the key `gcb:direct` (Bukkit name `direct`), fails with "folder
  contents does not seem to be a valid world", although `/mv import direct
  normal` adopts that same loaded world.

Requests that name an existing world by exactly the name it is registered under
are refused correctly. Plugins calling `WorldManager.createWorld`, `importWorld`
and `cloneWorld` see the same results.

## Task

Repair the plugin so that creating, importing and cloning recognise an existing
world through either identity of the request:

- `createWorld`, `importWorld` and `cloneWorld` fail with `WORLD_EXIST_LOADED`
  when the requested name or key belongs to a loaded Multiverse world and with
  `WORLD_EXIST_UNLOADED` when it belongs to an unloaded one. This includes a
  requested name that is another world's key path (`the_end`) and a requested
  key that belongs to a world created from that key (`gcb:keyed`). A rejected
  request creates, copies and loads nothing (no new Bukkit world, no new world
  folder) and `getWorlds()` is unchanged.
- A request that names an existing world by the name it is registered under keeps
  failing exactly as before, and the order of the checks is unchanged: the loaded
  check precedes the unloaded check, and both precede the folder checks.
- `importWorld` adopts a Bukkit world that is already loaded when the request
  addresses it by key, exactly as it already does when the request addresses it
  by name: the import succeeds with the running Bukkit world instance, and the
  imported world keeps that world's key and name and resolves by both.
- Lookups keep resolving both the name and the key string; creating, cloning,
  unloading and removing worlds by name keep working, and every upstream test
  keeps passing.

Keep the change inside `plugin/src/main/java`. The build files, the Gradle
wrapper and the existing tests under `plugin/src/test` are frozen: the verifier
restores them from the starter before building, and every existing upstream test
must keep passing.

## Evaluation

The verifier builds the plugin offline with the repository's Gradle wrapper
(`shadowJar`), runs the upstream MockBukkit test suite, and then loads the built
jar into a real Paper 1.21.11 dedicated server without players. There it
creates flat worlds by name and by key, unloads them, creates a Bukkit world
directly through Paper's `WorldCreator.ofKey`, and calls `createWorld`,
`cloneWorld` and `importWorld` with names and keys that do or do not collide
with existing worlds, all through the public `WorldManager` API, checking the
failure reasons, the Bukkit worlds, the world folders and `getWorlds()`.
