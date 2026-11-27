# Running the Hub

This page is the reference for the commands the [README](../README.md) summarizes.
All commands run inside `devenv shell` from the repository root.

## Discover games, packs and tasks

```sh
rhenium games
rhenium packs [--game <game-id>]
rhenium tasks [--game <game-id>] [--pack <pack-id>]
```

For example, `rhenium tasks --game garrys-mod --pack darkrp` lists one pack.

Task identity is always canonical:

```text
<game-id>/<pack-id>/<task-id>
```

## Run agents on tasks

### Unattended: `rhenium benchmark`

```sh
rhenium benchmark dst                                               # every DST task, provider api
rhenium benchmark dst/core --provider codex                         # every task of one pack
rhenium benchmark dst/core/dsmmo-release-regressions --provider claude
```

The selector is a game, a game/pack or one game/pack/task. For each matching task,
`rhenium benchmark` creates a fresh anonymous `strict` attempt under `--attempts-dir`
(default `~/Projects/rhenium-attempts/attempt-<random>-<timestamp>`), lets the provider
implement it, and then the platform scores it exactly once with the chosen `--profile`
and security options, as `rhenium run` would. The attempt's `PROMPT.md` contains no
scoring command, and the agent is told not to run a scorer. Tasks run one after another;
a failed task does not stop the rest. Progress goes to stderr and a JSON summary
(task key, attempt, status, score, Hub run ID and the agent's exit status) to stdout.
The command exits 0 only when every task passed.

| Provider | Agent | Model and credentials | What the agent may do |
| --- | --- | --- | --- |
| `api` (default) | mini-swe-agent through the Hub | `RHENIUM_MODEL_*`, or the Web UI settings | run shell commands in the attempt directory; Rhenium credentials are withheld; not a sandbox |
| `codex` | `codex exec --sandbox workspace-write` | its own login, or `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `CODEX_MODEL` | edit and run commands inside the attempt directory; Codex's sandbox blocks writes elsewhere and, by default, network access from commands |
| `claude` | `claude --print --permission-mode acceptEdits --allowedTools Bash` | its own login, or `ANTHROPIC_*` | edit files and run any shell command; not a sandbox |

Rhenium's own variables (`RHENIUM_*`, `MSWEA_*`) are withheld from `codex` and
`claude`. Their output is kept as the run's trajectory under
`.rhenium/hub/model-runs/<id>/`, with API keys from the environment masked. Each run
records the agent, model, exit status and changed files, so
`rhenium report --game <game-id>` compares providers. `rhenium benchmark` reads simple
`KEY=value` lines from `.env` in the repository root without overriding variables that
are already set. Prepare the game's runtime first; without it every `full` evaluation is
incomplete.

### Interactive: `benchmark`

```sh
benchmark <game/pack/task> [mini|codex|claude] [strict|practice] [attempt-dir]
```

`benchmark` is the devenv shortcut for [`run-benchmark`](../run-benchmark). It loads
`.env`, copies the public exam into a fresh attempt directory outside the repository
(by default `~/Projects/rhenium-attempts/attempt-<random>-<timestamp>`), and starts
the agent there.

- `mini` (default) runs mini-swe-agent through the Hub, which scores the submission
  when the agent finishes. It needs `RHENIUM_MODEL_NAME` (or `MSWEA_MODEL_NAME` or
  `CODEX_MODEL`) and the model credentials from `.env`.
- `codex` and `claude` start that CLI interactively in the attempt directory with the
  exam prompt. The agent scores itself once through the exact `scripts/score-exam`
  command printed in the attempt's `PROMPT.md`.
- `strict` (default) allows one scoring run after the implementation is complete.
  `practice` allows rescoring, and its result is not a comparable one-shot result.
  See the exam rules in [`AGENTS.md`](../AGENTS.md#12-exam-isolation-rules).

## Score an existing submission

```sh
rhenium run dst/core/dsmmo-release-regressions /path/to/submission
rhenium run garrys-mod/addons/prop-ownership-quota-registry C:\path\to\addon
rhenium run garrys-mod/addon-repairs/wiremod-e2-library-regressions /path/to/workspace
```

### Profiles

`core` and `full` are explicit evaluation profiles; `full` is the default. For DST and
GMod, only `full` can produce a complete pass, and only when all dedicated-server
assertions run. DST `full` requires the pack's prepared container runtime:
`dst/dst-dedicated-24700372` for `dst/core` and `dst/dst-dedicated-24700372-construct`
for `dst/construct`. For Stardew Valley and Isaac, `full` additionally requires the
pinned owned game build and all headless real-game assertions. Left 4 Dead 2 `full`
requires its prepared anonymous dedicated-server runtime and frozen real-server
assertions. A `core` result is incomplete and cannot pass an engine-backed plugin.

### Security modes

These commands use the compatibility-default `honest` security mode: suitable for trusted
development/reference work, but not a hostile-code sandbox. Formal model-generated or external
submissions require an independently installed disposable-host provider and immutable image:

```sh
rhenium run dst/core/dsmmo-release-regressions /path/to/submission \
  --security-mode untrusted \
  --host-provider <provider-id> \
  --host-image <immutable-image-or-snapshot-id>
```

Untrusted mode fails closed and never falls back to the local evaluator. Rhenium does not yet
ship a real disposable-host provider; see [Disposable evaluation hosts](disposable-evaluation-hosts.md).

## Prepare game runtimes

Authentication and runtime preparation are explicit operator actions; evaluation never
logs in, downloads, updates or rebuilds a runtime. Each game page under
[`docs/games/`](games/README.md) gives its exact runtime keys and prerequisites.

```sh
rhenium auth login steam            # licensed Steam games
rhenium auth login container        # digest-pinned public images
rhenium runtime list --game <game-id>
rhenium runtime prepare <game-id>/<runtime-id>
rhenium runtime verify <game-id>/<runtime-id>
```

See [Managed authentication and runtimes](managed-runtimes.md) for the lifecycle,
state and security boundary.

## Web UI

```sh
hub                 # first run builds web/dist, then serves http://127.0.0.1:4317
hub --port 4318     # any `rhenium web` option
```

`hub` runs `rhenium web`, which refuses non-loopback bind addresses. After changing
the frontend, rebuild it with `npm run build --prefix web`. See the
[Web UI guide](../web/README.md) for the Vite development server.

## CLI reference

```sh
rhenium games
rhenium packs [--game <game-id>]
rhenium tasks [--game <game-id>] [--pack <pack-id>]
rhenium auth list|status
rhenium auth login|logout <provider> [--account <alias>]
rhenium runtime list [--game <game-id>]
rhenium runtime doctor|verify|prune <game-id>/<runtime-id>
rhenium runtime prepare <game-id>/<runtime-id> [--account <alias>]
rhenium evaluation-host list|doctor
rhenium run <game/pack/task> <submission> [--profile core|full] [--security-mode honest|untrusted]
rhenium benchmark <game>[/<pack>[/<task>]] [--provider api|codex|claude] [--attempts-dir <dir>]
rhenium report [--game <game-id>] [--pack <pack-id>]
rhenium web
```

Set `RHENIUM_BENCHMARK_PATH` to one or more roots separated by the operating
system path separator. The default is `benchmarks/`. Generated output always
goes to `.rhenium/hub/`, never back into a benchmark directory. The other
variables are listed in [`.env.example`](../.env.example).

## API

The public hierarchy mirrors canonical identity:

```text
GET  /api/games
GET  /api/games/{game_id}/packs
GET  /api/tasks?game=&pack=&lang=
POST /api/games/{game_id}/packs/{pack_id}/tasks/{task_id}/runs
GET  /api/reports?game=&pack=
GET  /api/health
GET  /api/auth/providers
POST /api/auth/providers/{provider_id}/login
GET  /api/runtimes
POST /api/runtimes/{game_id}/{runtime_id}/prepare
GET  /api/operations/{operation_id}
GET  /api/evaluation-hosts
GET  /api/evaluation-hosts/{provider_id}/doctor
```

Health reports all loaded plugins and packs, isolated discovery errors, and
runtime degradations instead of presenting one implicit game/runtime.
Auth, runtime, and operation routes are documented in
[Managed authentication and runtimes](managed-runtimes.md#management-api).
Mutating management routes are loopback-only.

## Core-only installation

Core source distributions explicitly include only the core package, project
metadata and ignore policy, README, and built Web assets. They do not traverse
benchmark packs, datasets, plugin/provider projects, local state, or virtual
environments, including when building from a linked Git worktree. Build the Web UI
before release packaging; the checked-in `web/dist/.keep` supports editable installs
before that build.

The `rhenium` wheel is intentionally usable without a game plugin:

```sh
uv build --package rhenium
python -m pip install dist/rhenium-0.6.0-py3-none-any.whl
rhenium games
```

The last command returns an empty list when no plugin distributions are
installed. Install a game distribution such as `rhenium-dst` or
`rhenium-garrys-mod` separately; managed runtimes may also require their
independent provider distribution, such as `rhenium-container` or
`rhenium-steam`.
