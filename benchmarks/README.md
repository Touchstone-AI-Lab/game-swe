# Benchmark packs

`RHENIUM_BENCHMARK_PATH` points to one or more roots. The Hub recursively finds
every `benchmark.json`; a pack directory does not need to match its game or pack
ID.

```text
<benchmark-root>/<any-directory>/
├── benchmark.json       Schema-v2 plugin and pack selection
├── catalog.json         Plugin-owned catalog
├── exams/               Optional authored public documents
└── private/              Optional evaluator-owned assets
```

Every manifest has a stable `pack_id`, plugin ID, and relative catalog path.
Task keys are formed as `<game-id>/<pack-id>/<local-task-id>`.

Pack directories are immutable inputs. Public manifests, starter workspaces,
caches, run logs, and reports are written below `.rhenium/hub/`. Private assets
must never be copied into public starters or anonymous attempts.

See [Adding a game benchmark](../docs/adding-a-game.md).
