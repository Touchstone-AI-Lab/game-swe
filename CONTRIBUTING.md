# Contributing

Game integrations are separate workspace distributions so teams can work in
parallel without importing, editing, or installing another game's runtime.

## Game-owned changes

1. Claim one unique lowercase game ID and document maintainers.
2. Work under `plugins/<game>/`, `benchmarks/<pack>/`, and
   `docs/games/<game>.md`.
3. Register the plugin through `rhenium.benchmarks`; do not edit a central
   registry or add a core import.
4. Keep engine-only dependencies in the plugin `pyproject.toml`.
5. Add plugin-owned tests and run all repository checks.

For one game with multiple maintainers, keep one shared adapter. Divide work by
pack or task group, and require the game maintainers to review runtime/evaluator
changes.

## Shared core changes

Changes under `src/rhenium/`, shared scripts, identity, database, or API need:

- an explanation of the cross-game requirement;
- coverage with two independent plugin packages;
- collision tests using the same local task ID;
- proof that core-only installation stays free of engine dependencies;
- review from maintainers of more than one affected game when available.

Never add a game default, game-name conditional, private asset path, or legacy
compatibility import to core.

## Provider changes

Authentication providers are independent distributions under `providers/<provider>`
and register through `rhenium.auth_providers`. Keep provider-specific source schemas,
protocol adapters, helper manifests, and account behavior out of game plugins and
core conditionals. Protocol or helper changes require fake-helper unit coverage,
reviewed release hashes, and a clean download test on every claimed platform. See
[Managed authentication and runtimes](docs/managed-runtimes.md) and the
[Steam provider guide](providers/steam/README.md).

## Security and data handling

- Benchmark packs are read-only inputs.
- Anonymous attempts may contain public contracts only.
- Canonical keys, pack paths, private assertions, secrets, and prior results
  must not appear in anonymous output or model trajectories.
- Runtime and evaluator failures fail closed and remain isolated to their pack.
- Provider session secrets are plaintext local state in 0.6; never expose them in
  logs, API views, frontend state, test fixtures, or artifacts.
- Licensed source caches and evaluator images are local and non-redistributable.

## Required checks

Inside `devenv shell`, `check` runs the complete list from
[`AGENTS.md`](AGENTS.md#9-required-verification), which includes:

```sh
ruff check src plugins providers tests
mypy src plugins providers tests
pytest -q
npm run lint --prefix web
npm run test --prefix web
npm run build --prefix web
shellcheck run-benchmark scripts/prepare-exam scripts/score-exam \
  providers/steam/helper/build-helper.sh
git diff --check
```

Engine-backed tests may skip only when the documented engine is unavailable.
Stable status additionally requires the claimed runtime matrix to run in CI or
a controlled release environment.
