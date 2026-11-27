# Architecture

Rhenium 0.6 is a multi-game Hub. The dependency direction is one-way: plugins
depend on the public core contract; the core never imports or names a game.

```text
                  rhenium.benchmarks + rhenium.auth_providers
                                      │
          ┌──────────────────────┬──────────────────────┐
          │                      │                      │
 rhenium-dst plugin  rhenium-garrys-mod plugin  rhenium-contract-plugin
          │                      │                      │
          └──────────────────────┴───────────┬──────────┘
                                      │
benchmark roots ── recursive manifest scan ── BenchmarkHub
                                      │
                     ┌────────────────┼────────────────┐
                     │                │                │
                  CLI/API       DB schema v4     agent/reporting
```

## Repository layout

```text
src/rhenium/                 Game-neutral core only
plugins/dst/                 Independent rhenium-dst distribution
plugins/isaac-rebirth/       Independent rhenium-isaac-rebirth distribution
plugins/stardew-valley/      Independent rhenium-stardew-valley distribution
plugins/garrys-mod/          One rhenium-garrys-mod owner for the Addons, DarkRP and addon-repair packs
plugins/left-4-dead-2/       Independent rhenium-left-4-dead-2 distribution
plugins/rimworld/            Independent rhenium-rimworld distribution
plugins/mindustry/           Independent rhenium-mindustry distribution
plugins/minecraft/           Independent rhenium-minecraft distribution
plugins/slay-the-spire/      Independent rhenium-slay-the-spire distribution
plugins/palworld/            Independent rhenium-palworld distribution
plugins/balatro/             Independent rhenium-balatro-plugin distribution
plugins/terraria/            Independent rhenium-terraria distribution
plugins/contract/            Internal dependency-free contract distribution
tools/authoring/             Clean-room SWE-like data and benchmark authoring tool
tools/study/                 Controlled model studies (E0/E1/E2); never scores
providers/steam/             Independent Steam auth and depot provider
providers/container/         Independent digest-pinned public-image provider
providers/local-files/       Independent explicit local-file snapshot provider
providers/official-download/ Independent pinned official HTTPS download provider
web/                         React/Vite/shadcn local Hub UI
benchmarks/<pack>/           Read-only manifests, catalogs, and evaluator assets
docs/games/                  Ownership and support matrices
tests/                       Core and Hub contract tests
.rhenium/hub/                Generated state, workspaces, logs, and public manifests
```

Game plugins are discovered from `rhenium.benchmarks`; auth providers are discovered
independently from `rhenium.auth_providers`.
The core package has no DST import convention, registry entry, dependency, or
default game.

## Boundaries

### Core distribution

`src/rhenium/` contains orchestration, CLI, API, database, agent runner, shared
catalog models, identity, manifest validation, and normalized evaluation
results. Its dependency graph contains no DST package, `lupa`, or
`tree-sitter-lua`.

### Plugin distributions

Each `plugins/*` member is independently buildable and registers exactly one
entry point in `rhenium.benchmarks`. A plugin owns its game-specific catalog
types, evaluator, analyzer, runtime probes, public tools, and optional engine
dependencies. There is no in-tree import convention and no central game
registry.

### Benchmark packs

`RHENIUM_BENCHMARK_PATH` accepts one or more roots. The Hub recursively scans
for schema-v2 `benchmark.json` files. Packs contain versioned input data; the
Hub treats their directories as read-only.

### Auth providers and managed runtimes

Auth providers own QR/device login and licensed-source acquisition. The Hub stores
opaque provider sessions, resolves pack runtime catalogs, and runs explicit lifecycle
operations. Game plugins transform acquired sources into immutable evaluator artifacts.
Linux engine runtimes run only on a declared host platform; there is no Windows
execution worker. A plugin may own a native Windows-only runner for a separately prepared,
non-licensed server when it performs no acquisition, login, update, or build.

Session secrets are opaque to core consumers but are currently plaintext JSON in the
local SQLite database. Runtime preparation is the only lifecycle stage allowed to
acquire or build; evaluators receive ready `RuntimeArtifact` values and fail closed
when one is absent. The executable contract and security boundary are documented in
[Managed authentication and runtimes](managed-runtimes.md).

### Disposable evaluation hosts

Local evaluators and managed runtimes are development/runtime mechanisms, not a common
hostile-code sandbox. The optional `rhenium.evaluation_hosts` extension point owns disposable
host implementations. Core owns the provider-neutral lifecycle, strict `honest`/`untrusted`
mode distinction, proof validation and fail-closed behavior. In `untrusted` mode the complete
evaluation executes through the selected provider; core never falls back to the local plugin
evaluator. See [Disposable evaluation hosts](disposable-evaluation-hosts.md).

## Identity

Identifiers are namespaced at every stateful boundary:

```text
PluginDescriptor.id                    dst
PackKey                                dst/core
TaskKey                                dst/core/dsmmo-release-regressions
```

Database Task rows use canonical `task_key` as their primary key and also store
`game_id`, `pack_id`, `local_task_id`, catalog ID, and catalog version. Attempt,
Run, and Job payloads refer to canonical task keys. Two packs may therefore use
the same local task ID without sharing rows, workspaces, runs, or reports.

## Hub loading and fault isolation

Startup has two independent discovery phases:

1. Load entry points, rejecting duplicate plugin IDs/game IDs and isolating
   import failures.
2. Load every discovered manifest, bind it to a plugin and context, then reject
   duplicate pack/task keys.

A broken manifest, missing plugin, import error, or unavailable engine does not
prevent healthy games from loading. `/api/health` reports discovery errors and
runtime degradations. Runtime availability is observational; it does not cause
another pack to disappear.

## Plugin context and profiles

Every loaded pack receives an immutable `BenchmarkContext`:

- `pack_root`: read-only catalog and private evaluator input;
- `state_dir`: generated public manifests and starter workspaces;
- `cache_dir`: plugin cache scoped to the pack;
- `project_root`: repository context for maintained in-repo assets.

Evaluators receive a named profile, not a runtime boolean. A plugin declares
the profiles it supports, its default, and whether each profile is eligible to
produce a complete result. Core rejects `passed=true` for an incomplete result.

## Generated state

The default layout is:

```text
.rhenium/hub/
├── state.sqlite
├── cache/plugins/<game>/<pack>/
├── packs/<game>/<pack>/
│   ├── public/tasks.json
│   └── workspaces/<local-task-id>/
├── runs/<run-id>/runtime.log
├── tools/steam/<version>/
├── cache/providers/<provider>/<fingerprint>/
├── cache/runtimes/<game>/<runtime>/
└── model-runs/<model-run-id>/
```

The Hub opens only schema-v4 state. Any other database fails with backup/fresh-state
instructions instead of being mutated; there is no upgrade path from earlier schemas.

## Validation scope

- Complete now: core multi-plugin contract and dependency-free multi-plugin Hub
  verification.
- Engine-backed now: DST through its managed Linux container runtime, and the
  Garry's Mod DarkRP and addon-repair packs through managed Linux GLuaTest
  containers, and the Garry's Mod Addons pack through its operator-prepared native
  App 4020 runtime, all Experimental.
- One `rhenium-garrys-mod` plugin owns `garrys-mod/addons`, `garrys-mod/darkrp` and
  `garrys-mod/addon-repairs`. The Addons pack keeps its native App 4020 runner and
  has no managed runtime key. Each GLuaTest pack binds its own runtime key to the
  same digest-pinned GLuaTest source image and prepares its own evaluator images.
