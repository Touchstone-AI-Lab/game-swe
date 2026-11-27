# Maintenance notes: multiverse-core-case-insensitive-world-names

## Upstream

- Repository: https://github.com/Multiverse/Multiverse-Core (BSD-3-Clause,
  `LICENSE.md` kept in the starter).
- Base commit: `1434ca176aac92e2724695fe1d14b3f84a9a3939` (parent of the fix).
- Fix: merge commit `aac0111ddeea3c16aacef20eea92632dca72745f` of PR #3408
  "Fix case-insensitive world name handling" (head `f66e673e`, merged
  2026-01-01, shipped in Multiverse-Core 5.5).
- The starter is `git archive` of the base commit without `.github/`, `docs/`
  (only a `.keep`) and `config/` (release images and a Doxygen file that do
  not take part in the build).

## Defect

`WorldManager` keeps `worldsMap` and `loadedWorldsMap` as plain `HashMap`s and
lower-cases keys on `put` and in every lookup, but removes and re-reads entries
with the raw world name in three places:

- `removeLoadedMultiverseWorld` (`unloadWorld`): `loadedWorldsMap.remove(name)`
  returns null for a mixed-case name and `Objects.requireNonNull` throws the
  "loaded world isn't in the map... BUGGG" NPE. The Bukkit world has already been
  unloaded at that point, so Multiverse keeps reporting a world as loaded that
  the server no longer has.
- the same method's `worldsMap.get(name)`, which the NPE above hides;
- `removeWorldFromConfig` (`removeWorld`, `deleteWorld`): `worldsMap.remove(name)`
  removes nothing, so the world config and `worlds.yml` entry are gone while the
  registry still lists the world.

Every lifecycle operation that unloads or forgets a world inherits one of these:
unload, load-after-unload, remove of a loaded world (unloads first), remove of an
unloaded world (leaks), delete (unload + remove) and regen (delete + create; the
create is then rejected because the leaked entry still exists).

## Reference fix

`solution/after/` carries the upstream main-source change only: a new
`utils/CaseInsensitiveStringMap` and `WorldManager` switching both maps to it.
The upstream PR also renamed a fixture in `WorldManagerTest.kt` to `World2`;
that test change is not part of the task because `src/test` is frozen at the
base commit (the base tests pass with and without the fix).

## Build

Gradle 8.10.2 wrapper, convention plugin `org.mvplugins.multiverse-plugin`
1.2.2, `paper-api 1.21.8-R0.1-SNAPSHOT`, tests in Kotlin with MockBukkit
4.84.0. The convention plugin disables the plain `jar` task, so the artifact is
`shadowJar` → `build/libs/multiverse-core-local.jar`. Gradle resolves the JUnit
platform launcher only while running tests, so the image warm-up runs `test`
online once before the offline proof.

## Why the repository matters

The exam reports only operator-visible symptoms (`/mv unload` failing, worlds that
stay registered after `remove`/`delete`/`regen`). The solver must find the world
registry in `WorldManager`, notice that keys are normalised on insertion and
lookup but not on removal, and repair every removal site, or change the maps
themselves as upstream did. A patch to the unload site alone still leaks on
remove, delete and regen; lower-casing world names on creation makes the
lifecycle cases pass but breaks the original-name contract; dropping the
normalisation breaks case-insensitive lookups and two upstream unit tests.

## Live-server design

All server cases use the public `WorldManager` API through `MultiverseCoreApi`,
with flat worlds (fixed seed), no structures, no spawn adjustment and no player.
Each case uses its own world name. A call that throws is reported as the failure
of that step (`call(...)` turns the exception into an assertion message), so the
starter's NPE shows up as the case failure.

- `plugin is enabled` (sentinel).
- `world lookups ignore case` (preserved): `GcbLookup` resolves through
  `isWorld`/`isLoadedWorld`/`getWorld`/`getLoadedWorld` under four casings, an
  unknown name does not, and `getWorlds()` lists it once.
- `worlds keep the name they were created with` (preserved): `getName()`, a
  lookup under another casing, the Bukkit world, the folder and the `worlds.yml`
  key all keep `GcbKeepName`.
- `lower-case world goes through its whole lifecycle` (preserved): `gcb_lower`
  unload, load again, remove (folder kept); `gcb_lower_gone` delete (folder gone).
- Targets (all fail on the starter): `mixed-case world can be unloaded`,
  `mixed-case world can be loaded again`, `loaded mixed-case world can be
  removed`, `unloaded mixed-case world can be removed`, `mixed-case world can be
  deleted`, `mixed-case world can be regenerated` (new seed, listed once, loaded,
  original name, `worlds.yml` entry kept).

Target cases look a world up by its original name when they need it to be found
and check every casing only where it must not be found (not loaded after unload,
forgotten after remove/delete), so a submission that drops case-insensitive
lookups fails only the lookup contract case and the two case-insensitivity unit
tests, not the lifecycle targets.

## Merge review (0.2.0)

The neighbouring history holds no second fix of the same defect family: the lower-cased registry keys were introduced by PR #3394 ("Make world name matching case-insensitive", 2025-12-08), a feature, and the PRs merged into `v5.5-2` right after #3408 (#3409 world border safety, #3411 enforce delay, #3412 world change priority, ...) touch other code. The task keeps PR #3408 alone and grows by covering every lifecycle operation it repairs.
