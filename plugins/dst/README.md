# rhenium-dst

Independent Don't Starve Together plugin for the Rhenium benchmark Hub.

The package owns the DST catalog models, the tree-sitter Lua analyzer, the
plain-Lua sandbox, both evaluators, the public syntax checker, and the
dedicated-server runtime integration. Its game data remains in the repository's
`benchmarks/dst/` (repair) and `benchmarks/dst-construct/` (construct) packs.
The plugin picks the machinery by catalog id.

A repair task (catalog `dst-core`) is a real open-source mod with upstream fixes
reverted. The workspace holds the mod tree under `mod/`. The evaluator checks the
submission's shape (required files, no symbolic links or native modules,
parseable Lua) and then loads the mod on the pinned headless dedicated server with
the task's hidden suite. The suite's nonce-bound case list must match the
catalog's frozen `server_cases` exactly. A complete run also reports
`runtime.caseOutcomes`.

A construct task (catalog `rhenium-dst-v2`, `fixed-v1.json`) asks for a mod
written from an empty workspace, which is the submission root. Its evaluator
(`construct_evaluator.py`, with `construct_catalog.py` and `lua_runner.py`) scores
required files, Lua syntax, a sandboxed plain-Lua suite run with `lupa`, an
implementation-depth gate, regex integration contracts and the dedicated-server
suite. It is the evaluator those tasks were validated with before the repair pack
replaced them in `benchmarks/dst/`.

```sh
python -m rhenium_dst.public_check /path/to/workspace/mod   # repair workspace
python -m rhenium_dst.public_check /path/to/submission      # construct submission
```

Runtime paths use `RHENIUM_PLUGIN_DST_ROOT` and
`RHENIUM_PLUGIN_DST_SERVER_BIN`. Core Rhenium does not read these variables.
