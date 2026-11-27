# GameCodeBench

English | [简体中文](README.zh-CN.md)

GameCodeBench is a benchmark for coding agents on real game-engineering work:
repairing and writing mods, plugins and scripts for real games, graded by the real
game engine or dedicated server wherever the task allows. The `rhenium` Hub
discovers task packs, runs agents in isolated attempt directories and scores their
submissions. Every game is an independent plugin.

> [!NOTE]
> Version 0.6 is a research preview. Every game integration is Experimental or In
> Development, and controlled post-integration runtime validation is still required.
> No game files are part of this repository: licensed games and servers are prepared
> locally.

## Supported games

| Game | Status | Submission language |
| --- | --- | --- |
| [Don't Starve Together](docs/games/dst.md) | Experimental | Lua |
| [Garry's Mod](docs/games/garrys-mod.md) | Experimental | Lua (GLua) |
| [Palworld](docs/games/palworld.md) | Experimental | Lua (UE4SS) with a JSON manifest |
| [Balatro](docs/games/balatro-container-v1.md) | Experimental | Lua with JSON mod metadata |
| [The Binding of Isaac: Rebirth](docs/games/isaac-rebirth.md) | In Development | Lua |
| [Left 4 Dead 2](docs/games/left-4-dead-2.md) | In Development | SourcePawn, Squirrel |
| [Stardew Valley](docs/games/stardew-valley.md) | In Development | C# |
| [RimWorld](docs/games/rimworld.md) | In Development | C# |
| [Terraria](docs/games/terraria.md) | In Development | C# |
| [Mindustry](docs/games/mindustry.md) | In Development | Java |
| [Minecraft](docs/games/minecraft.md) | In Development | Java |
| [Slay the Spire](docs/games/slay-the-spire.md) | In Development | Java 8 |

Versions, platforms and validation evidence are in the
[full support matrix](docs/games/README.md).

## Contributors

| Contributor | Games |
| --- | --- |
| Xingzhi Li | Rhenium Hub; Don't Starve Together, Garry's Mod, The Binding of Isaac: Rebirth, Mindustry, Minecraft, Stardew Valley |
| Hui Shen | Don't Starve Together |
| Changyi Yang | Garry's Mod, Slay the Spire |
| Yunta Hsieh | Garry's Mod |
| Xuesong Ye | The Binding of Isaac: Rebirth |
| Zhuhan Bao | The Binding of Isaac: Rebirth, Minecraft |
| Zhuoran | Left 4 Dead 2, Terraria |
| Jiaxuan Luo | Stardew Valley |
| Zhengshen He | RimWorld |
| Yunge | Mindustry |
| Rui Hu | Palworld |
| Guobin Zhang | Palworld |
| Sangyu Pan | Balatro |

## Requirements

- [Nix](https://nixos.org/download) and [devenv](https://devenv.sh/getting-started/).
  The dev shell provides Python 3.12, Node.js and every plugin.
- Docker, for games whose engine runs in a Linux x86_64 container.
- Some games need a licensed copy or a specific host setup. Palworld and Balatro
  provide explicit Linux runtime preparation through `rhenium runtime prepare`.
  Each game page lists the measured builds and required setup.

## Quick start

```sh
git clone git@github.com:Touchstone-AI-Lab/game-swe.git
cd game-swe
cp .env.example .env    # add your model API key
devenv shell
```

Inside the shell:

```sh
rhenium tasks --game dst                                  # list tasks
rhenium benchmark dst --provider claude                   # an agent solves every DST task
rhenium benchmark dst/core/dsmmo-release-regressions      # one task, default provider api
rhenium run dst/core/dsmmo-release-regressions ./my-mod   # score an existing submission
hub                                                       # Web UI at http://127.0.0.1:4317
```

- `rhenium benchmark <game>[/<pack>[/<task>]] --provider api|codex|claude` runs
  unattended. Each task gets its own anonymous attempt, the agent implements it, and
  the platform scores it exactly once; a JSON summary follows. `api` (default) is
  mini-swe-agent with the `RHENIUM_MODEL_*` settings; `codex` and `claude` are the
  installed CLIs with their own login or the keys in `.env`. Prepare the game's
  runtime first.
- `benchmark <task> [mini|codex|claude] [strict|practice]` opens one attempt
  interactively instead, and the agent runs the scorer itself.
- `rhenium run` uses the trusted `honest` mode, which is not a sandbox for hostile
  code. [Running the Hub](docs/usage.md) covers profiles, security modes and every
  command.

## Prepare a game runtime

Engine-backed tasks need their pinned game or dedicated server, prepared once:

```sh
rhenium runtime list --game dst                      # show the runtime keys
rhenium auth login container                         # or `steam` for licensed games,
                                                     # or `official-download` for non-Steam servers
rhenium runtime prepare dst/dst-dedicated-24700372
```

Scoring never logs in or downloads anything. Without the runtime, a `full`
evaluation is incomplete and does not pass. Each game page gives its runtime keys.

## Repository layout

```text
src/rhenium/    Game-neutral Hub core: CLI, API, database, agent runner
plugins/        One independent distribution per game
benchmarks/     Read-only task packs: exams, starters, evaluators
providers/      Auth and runtime source providers (Steam, container, local files, official downloads)
web/            Local Web UI (React, Vite)
tools/          Authoring and study tooling
docs/           Documentation; docs/games/ has one page per game
```

## Documentation

- **Using:** [Running the Hub](docs/usage.md) ·
  [Managed authentication and runtimes](docs/managed-runtimes.md) ·
  [Disposable evaluation hosts](docs/disposable-evaluation-hosts.md) ·
  [Web UI](web/README.md)
- **Games:** [Supported games](docs/games/README.md) ·
  [Status definitions](docs/statuses.md)
- **Extending:** [Architecture](docs/architecture.md) ·
  [Plugin contract](docs/plugin-contract.md) ·
  [Adding a game](docs/adding-a-game.md) ·
  [Clean-room authoring](tools/authoring/README.md) ·
  [Contributing](CONTRIBUTING.md)

Every page is listed in the [documentation index](docs/index.md).

## Development

```sh
check    # ruff, mypy, pytest, web lint/test/build, shellcheck, git diff --check
```

Contributors and coding agents follow [AGENTS.md](AGENTS.md): Conventional
Commits, no edits to frozen benchmark assets, and the full check list before
handoff.
