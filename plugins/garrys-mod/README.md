# rhenium-garrys-mod

The single Garry's Mod plugin for the Rhenium benchmark Hub. It serves three packs
through the `garrys-mod` game ID, with two task models chosen by catalog identity:

| Pack | Directory | Catalog | Tasks | Task model | Runtime |
| --- | --- | --- | ---: | --- | --- |
| `garrys-mod/addons` | `benchmarks/gmod/` | `rhenium-gmod-v2` | 5 | Clean-room Addon written from an empty workspace | Operator-prepared native App 4020 server (no managed runtime key) |
| `garrys-mod/darkrp` | `benchmarks/darkrp-core/` | `darkrp-core` | 7 | Repair of the `darkrp/` gamemode tree | `garrys-mod/gmod-gluatest-darkrp` |
| `garrys-mod/addon-repairs` | `benchmarks/gmod-addon-repairs/` | `gmod-addon-repairs` | 5 | Repair of one upstream addon, e.g. `wire/` | `garrys-mod/gmod-gluatest-addons` |

The repository-maintenance authoring tool can also stage clean-room gamemode repairs
in a separate synth pack (catalog `garrys-mod-clean-room-synth`, runtime key
`garrys-mod/gmod-gluatest-synth`); no such pack ships in this repository.

Both subsystems live below the distribution's single Python namespace:

```text
src/rhenium_garrys_mod/
├── plugin.py       unified `rhenium.benchmarks` entry point; dispatches by catalog ID
├── addons/         clean-room Addon catalog, public analyzer, isolated plain-Lua
│                   verifier, evaluator, and native Windows/Linux runners
└── darkrp/         GLuaTest task model, evaluator and managed runtime builder
                    (shared by every GLuaTest pack; the module keeps its historical name)
```

## Addons pack (native App 4020)

For Addon scoring on Windows, set
`RHENIUM_PLUGIN_GMOD_SERVER_ROOT` to the immutable App 4020 installation at
build `23150012`; per-run server views require the Rhenium state directory and
server to share an NTFS volume. Evaluation never invokes SteamCMD, downloads or
updates the server. `core` is incomplete; `full` requires the real Dedicated
Server and both Phase A/B processes.

For native Linux x86_64, use the separately pinned `linux_build_id` from the
catalog and the same explicit `RHENIUM_PLUGIN_GMOD_SERVER_ROOT` setting. The
stable server is a 32-bit x86 ELF and needs the matching Linux loader/libraries.
State and server must share a filesystem for per-run hard-linked views. The
runner executes `srcds_linux` directly, uses a fresh POSIX process group per
phase, bounds output, terminates timed-out descendants, and reuses only the
task-scoped data directory between phases. It never invokes `srcds_run` or
SteamCMD. See [Linux setup](../../docs/games/garrys-mod.md#native-linux-runtime).

Windows Job Objects, Linux process groups and per-run server views provide
lifetime control, not an untrusted-code security sandbox.

## GLuaTest packs (DarkRP and addon repairs)

A task declares `source_kind` (`gamemode` or `addon`) and, for addons, its
`starter_directory`. The evaluator stages the submitted tree at
`/app/<starter_directory>` (DarkRP: `/app/darkrp`), checks the matching shape (`lua/`
for an addon, `gamemode/` for a gamemode), and selects the runtime key by catalog
identity, so each pack keeps its own prepared images. Addon submissions may not ship
`lua/gluatest/` or `lua/tests/`, which would shadow the private harness or add
collected cases.

```sh
rhenium runtime prepare garrys-mod/gmod-gluatest-darkrp
rhenium runtime prepare garrys-mod/gmod-gluatest-addons
rhenium run garrys-mod/addon-repairs/<task-id> /path/to/workspace --profile full
```

`core` is always incomplete; only `full` runs the dedicated server. Containers,
nonce-bound audits and the static preflight are defense in depth, not an
untrusted-code sandbox: submitted Lua and the private suite share one Lua state.

Formal untrusted scoring of any pack still requires the disposable evaluation-host
boundary. See [Garry's Mod support](../../docs/games/garrys-mod.md).
