# Adding a game benchmark

This workflow gives each team an isolated plugin package and one or more data
packs. A new game never adds game-name branches or imports to `src/rhenium/`.

## 1. Claim identity and ownership

Choose normalized IDs such as `stardew-valley` and record maintainers in the
Supported Games table. One game ID has one plugin owner. Multiple maintainers
for the same game share the adapter and may own separate packs or task groups.

## 2. Create an independent plugin distribution

```text
plugins/stardew-valley/
├── pyproject.toml
├── README.md
├── src/rhenium_stardew_valley/
│   ├── __init__.py
│   └── plugin.py
└── tests/
```

Add the package to the existing `plugins/*` uv workspace pattern and register:

```toml
[project.entry-points."rhenium.benchmarks"]
stardew-valley = "rhenium_stardew_valley.plugin:StardewValleyBenchmarkPlugin"
```

Keep engine SDKs, parsers, and runtime libraries in this plugin's dependency
list. They must not be added to the root `rhenium` dependencies.

## 3. Implement the contract

Subclass `BenchmarkPlugin`, provide a `PluginDescriptor`, load the catalog from
the supplied pack root, and construct an evaluator from `BenchmarkContext`.
Use the optional hooks only for game-specific prompts, starters, public tools,
and agent guidance.

Define explicit evaluation profiles. `core` should be marked incomplete when
it omits assertions required for a real pass; `full` must fail closed if the
engine or server cannot execute its required assertions.

Game plugins do not implement or select the formal untrusted-host boundary. Keep the local
evaluator usable for `honest` development and runnable by a guest wrapper, but let core route
explicit `untrusted` evaluation through `rhenium.evaluation_hosts`. A plugin must not silently
fall back to local execution or claim that its container/process control is a hostile-code
sandbox. See [Disposable evaluation hosts](disposable-evaluation-hosts.md).

## 4. Add a schema-v2 benchmark pack

Packs may live in any directory below a configured benchmark root:

```text
benchmarks/stardew-core/
├── benchmark.json
├── catalog.json
├── runtimes.json             optional, for managed licensed runtimes
├── exams/
└── private/
```

```json
{
  "schema_version": 2,
  "pack_id": "core",
  "plugin": "stardew-valley",
  "catalog": "catalog.json"
}
```

`pack_id` is stable within a game. Public task identity becomes
`stardew-valley/core/<local-task-id>`. The pack is read-only: do not create
workspaces, logs, caches, or generated manifests below it.

Test discovery with:

```sh
RHENIUM_BENCHMARK_PATH="$PWD/benchmarks" rhenium packs --game stardew-valley
RHENIUM_BENCHMARK_PATH="$PWD/benchmarks" rhenium tasks --game stardew-valley --pack core
```

## 5. Add a managed runtime

Every game needs one. Each task is evaluated against the real game, or its official
dedicated server, running the submitted code; a source projection, stubbed engine
types, or a mod loader run without the game is not an evaluation. The runtime
acquires the game automatically during `rhenium runtime prepare` through the Steam
provider, pinned to an exact app, depot and build. Only a game that is not on Steam,
or whose official dedicated server is distributed only outside Steam, may instead
download that official distribution automatically, pinned to an exact version and
checked by SHA-256. The
[official-download provider](../providers/official-download/README.md) implements
that path: the runtime catalog pins each file's exact HTTPS URL, size and SHA-256.
Operator-supplied game files, hand-prepared installations and manual Harbor
workflows do not qualify (AGENTS.md, "Real game and automatic acquisition").

Do not put Steam login, depot download, credentials, or system-package installation
inside a game plugin. Select the independent runtime catalog from `benchmark.json`:

```json
{
  "schema_version": 2,
  "pack_id": "core",
  "plugin": "stardew-valley",
  "catalog": "catalog.json",
  "runtime_catalog": "runtimes.json"
}
```

`runtimes.json` declares provider-owned licensed sources, supported hosts, and
bindings from local task IDs to runtime IDs. The plugin returns a game-owned
`RuntimeBuilder` from `create_runtime_builder(context, spec)`. Its `doctor` hook is
read-only; `prepare` builds an immutable local artifact; `verify` checks that exact
artifact; and `prune` removes only resources owned by it. Evaluators consume the
`RuntimeArtifact` mapping supplied by core and never prepare implicitly.

Start from the complete examples and security rules in
[Managed authentication and runtimes](managed-runtimes.md#adding-a-managed-runtime-to-a-game).
Steam source fields and fake-helper testing are documented in the
[Steam provider guide](../providers/steam/README.md#licensed-source-schema).

Verify the operator path before claiming support:

```sh
rhenium auth list
rhenium runtime list --game stardew-valley
rhenium runtime doctor stardew-valley/<runtime-id>
rhenium auth login steam
rhenium runtime prepare stardew-valley/<runtime-id>
rhenium runtime verify stardew-valley/<runtime-id>
```

Rhenium has no Windows execution worker. A Windows support claim requires a
plugin-owned native Windows runner validated against the real engine on Windows.

## 6. Document actual support

Create `docs/games/stardew-valley.md` with:

- maintainers and one shared benchmark status;
- game distribution and exact build or rolling version policy;
- engine/mod API and loader versions;
- game platforms and benchmark-runner platforms separately;
- submission, evaluator, and toolchain languages;
- runtime prerequisites and unsupported configurations;
- catalog version, profiles, and compatibility policy.

Do not promote a game beyond Planned based on a skeleton or inferred tooling.

## 7. Verify isolation

At minimum, tests must demonstrate:

- core can install and start without this plugin or its dependencies;
- this plugin and the contract plugin load simultaneously;
- another pack may reuse the same local task ID without collisions;
- a read-only pack can list, prepare, and evaluate tasks;
- missing SDK/runtime and plugin import failures are isolated and visible in
  health;
- anonymous attempts expose no canonical key, private path, or private asset;
- profile validation and report filtering work in both CLI and API;
- a known-good fixture passes `full` in every claimed engine environment;
- provider sessions and operation responses never expose secrets;
- runtime pruning cannot remove another game or runtime's artifacts.

See [Plugin contract](plugin-contract.md),
[Managed authentication and runtimes](managed-runtimes.md),
[Architecture](architecture.md), and [Contributing](../CONTRIBUTING.md).
