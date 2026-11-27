# Rhenium repository agent rules

This file is normative for every coding agent working in this repository. The
terms **MUST**, **MUST NOT**, **SHOULD**, and **SHOULD NOT** have their RFC 2119
meanings. Passing tests does not excuse violating these rules.

If a requested change cannot be completed without violating a rule, the agent
MUST stop, explain the exact conflict, and request direction. An agent MUST NOT
delete, weaken, bypass, or reinterpret these rules merely to finish a task or
make a check pass. Changes to this file require an explicit repository-maintenance
request from the user.

## 1. Classify the task before acting

Every task is one of these modes:

- **Repository maintenance**: developing, reviewing, documenting, testing, or
  releasing Rhenium, its plugins, providers, Web UI, or benchmark packs.
- **Exam attempt**: solving or scoring a copied benchmark exam as the model under
  test.

The repository-maintenance rules apply by default. If the request is an exam
attempt, the exam-isolation section at the end of this file takes precedence.
An agent MUST NOT use maintenance access to inspect hidden benchmark material
during an exam.

## 2. Required working discipline

Before modifying files, an agent MUST:

1. read this file and any more specific nested `AGENTS.md`;
2. inspect `git status --short` and preserve all pre-existing user changes;
3. read the relevant contract and implementation rather than guessing behavior;
4. identify whether the change affects core, a game plugin, a provider,
   the Web UI, benchmark semantics, packaging, or a database schema;
5. keep the change no broader than the requested outcome.

A nested `AGENTS.md` MAY add or strengthen rules for its subtree. It MUST NOT
silently weaken root security, benchmark-integrity, or exam-isolation rules.

During implementation, an agent MUST:

- use repository abstractions and public contracts instead of duplicating logic;
- add or update tests for behavior changes and regressions;
- update documentation in the same change when commands, APIs, schemas, support
  claims, security boundaries, or operator workflows change;
- fail closed when a required engine, runtime, assertion, or verification step
  cannot run;
- report limitations truthfully; an untested path is not supported merely because
  it compiles or works in an emulator;
- keep generated state out of source and benchmark directories.

An agent MUST NOT:

- overwrite, discard, reformat, stage, or commit unrelated user work;
- edit tests, fixtures, checksums, or expected results just to hide a failure;
- use destructive Git commands such as `git reset --hard` or broad checkout/clean
  operations;
- run `sudo`, a system package manager, or a host installer unless the user has
  explicitly requested that exact host mutation;
- add secrets, licensed files, runtime caches, build outputs, model trajectories,
  or local databases to Git;
- claim completion while a required check is failing or silently omit an unrun
  check from the handoff.

## 3. Architecture invariants

### Game-neutral core

`src/rhenium/` MUST remain game-neutral and provider-neutral at its public
contract boundaries.

- Core MUST NOT import a game plugin, name a game as a default, contain
  game-specific paths, or depend on an engine SDK/runtime.
- Core MAY define generic plugin, auth-provider, runtime, operation,
  identity, database, CLI, API, and reporting contracts.
- A cross-game core change MUST have a real cross-game requirement and contract
  coverage using at least two independently packaged plugins where applicable.
- Core-only installation and startup MUST continue to work without game plugins,
  auth providers, or their dependencies.
- Canonical stateful identity is `<game-id>/<pack-id>/<task-id>`. Database rows,
  jobs, runs, reports, and APIs MUST NOT collapse identity to an unqualified local
  task ID.

### Game plugins

Each game integration MUST be an independent distribution under
`plugins/<game>/` and register through `rhenium.benchmarks`.

- Plugin-specific dependencies stay in that plugin's `pyproject.toml`.
- Plugins own game catalog types, prompts, starter materialization, evaluators,
  runtime probes/builders, and engine dependencies.
- A plugin MUST read pack inputs through `BenchmarkContext.pack_root` and write
  generated files only to its state/cache locations.
- A plugin MUST NOT write into a benchmark pack at runtime.
- A plugin MUST NOT add its game to a central registry or core conditional.
- `full` MUST run every assertion required for a complete result. If it cannot,
  the result MUST be incomplete and MUST NOT pass.
- `core` or another reduced profile MUST NOT be represented as a comparable full
  benchmark pass.

### Auth providers

Each auth provider MUST be an independent distribution under
`providers/<provider>/` and register through `rhenium.auth_providers`.

- Provider-specific login, refresh, source schemas, and acquisition behavior
  MUST NOT leak into game plugins or game-neutral core conditionals.
- Provider sessions and source objects are opaque outside their owning provider.
- Provider progress, challenges, errors, public views, and operation results MUST
  NOT expose session secrets.
- Unit tests MUST use fake/local helpers and MUST NOT require a real account,
  real token, licensed depot, or network connection.

### Managed runtimes

Licensed-runtime preparation MUST follow the contract in
[`docs/managed-runtimes.md`](docs/managed-runtimes.md).

- Authentication and preparation are explicit operator actions. Evaluation MUST
  NOT implicitly log in, download, update, or rebuild a runtime.
- `RuntimeBuilder.doctor()` and `verify()` MUST be read-only and MUST NOT install
  system packages.
- `prepare()` MUST consume the provider-acquired source and return the exact
  runtime key/fingerprint expected by core.
- Artifact identity MUST refer to immutable local content, such as a concrete
  Docker image ID, not only a mutable tag.
- `prune()` MUST remove only resources owned by the selected artifact and SHOULD
  be idempotent. It MUST NOT use an unresolved broad path or glob.
- A legitimate interactive step MUST use `RuntimeActionRequired` with non-secret
  details. It MUST NOT be silently skipped or treated as success.
- `RuntimeSpec.source.expectedFiles` and `source.sha256` are not automatically
  enforced by core or Steam provider v0.1.0. A game builder that declares them
  MUST explicitly validate and test them.
- Licensed source caches, client state, offline tickets, and evaluator images are
  local and non-redistributable. They MUST NOT be uploaded to public registries
  or included in wheels, releases, CI artifacts, or benchmark packs.

### Real game and automatic acquisition

- Every task MUST be evaluated against the real game: the game itself, or its
  official dedicated server, running the submitted code. A source projection,
  stubbed or doubled engine types, or a mod loader run without the game MUST NOT
  stand in for it, and a result that depends on one MUST NOT count as a full
  result.
- The game or dedicated server MUST be acquired automatically by
  `rhenium runtime prepare` through the Steam provider (a `steam-depots` source),
  pinned to an exact app, depot, and build. Operator-supplied game files,
  hand-prepared installations, and manual Harbor workflows do not satisfy this
  rule.
- Exception: when the game is not distributed on Steam, or its official dedicated
  server is distributed only outside Steam, the runtime MAY use that official
  distribution instead, provided preparation downloads it automatically, pins the
  exact version, and verifies its SHA-256. Operator-supplied files still do not
  qualify.
- New game integrations and changes to a runtime MUST meet these rules. A pack
  that does not yet meet them MUST NOT be described as meeting them.

### Native Windows engines

Rhenium has no Windows execution worker. A Linux engine runtime runs only on a host
platform declared in its `runtimes.json`; Windows support for it MUST NOT be
claimed.

A plugin-owned native Windows runner is permitted for a separately prepared,
non-licensed server when evaluation performs no login, acquisition, install,
update, or build. It MUST probe and pin the server version, fail closed on a
mismatch, keep generated state outside the benchmark pack, and use real native
engine evidence for support claims. GMod App 4020 is the current implementation
(GMod Addons). Preparing that server is subject to
[Real game and automatic acquisition](#real-game-and-automatic-acquisition).

- Rhenium MUST NOT enable Windows features or install WSL automatically.
- Windows support MUST NOT be claimed from a Docker build or a Linux test alone.

### Local Web UI

The UI under `web/` uses React, TypeScript, Vite, Tailwind, and the checked-in
shadcn-style primitives.

- Management UI/API access MUST remain loopback-only. An agent MUST NOT broaden
  bind addresses, CORS, proxying, or mutation access without an explicit reviewed
  authentication design.
- Frontend code MUST use relative `/api` routes and MUST NOT store provider
  secrets in browser storage, component state models, logs, analytics, or toasts.
- Reuse `src/components/ui` and shared theme tokens. Do not introduce a parallel
  component system or hard-coded light/dark palette without a design requirement.
- Preserve keyboard access, accessible labels, responsive navigation, operation
  polling, QR challenge rendering, and `action_required` states.
- A release wheel MUST contain a production-built `web/dist`, while
  `web/dist/.keep` MUST remain available so editable installation works before a
  frontend build.

## 4. Steam-specific security and release rules

The Steam implementation is documented in
[`providers/steam/README.md`](providers/steam/README.md).

- Rhenium MUST NEVER request, accept, log, or store a Steam password.
- Steam refresh tokens and Guard data currently live as plaintext JSON in local
  SQLite. Agents MUST treat `.rhenium/hub`, backups,
  logs, fixtures, screenshots, and process output as secret-bearing surfaces.
- `auth logout` removes only local state. It MUST NOT be documented as remotely
  revoking a Steam device.
- Helper resolution from `RHENIUM_STEAM_HELPER` or `PATH` is a development/local
  override. Released downloads MUST use a versioned manifest and pinned SHA-256.
- Private GitHub Release access MAY use authenticated `gh`, or
  `GH_TOKEN`/`GITHUB_TOKEN` when `gh` is absent. Tokens MUST NOT be committed or
  printed.
- An agent MUST NOT replace an asset under an existing helper release tag.
  Publish a new version, then update URLs and hashes together.
- Protocol changes require tests on both the Python parser/provider behavior and
  the patched helper, plus clean downloads on every claimed platform.
- Helper workflows currently upload build artifacts but do not create
  releases or update manifests automatically. Documentation MUST NOT claim that
  they do.
- Linux and Windows helpers are not platform code-signed; macOS is ad-hoc signed.
  SHA-256 provides integrity against the reviewed manifest, not an independent
  publisher signature. Claims MUST use this exact security boundary.

## 5. Benchmark integrity and frozen assets

Benchmark semantics are product data, not convenient test fixtures.

- Infrastructure, runtime, UI, documentation, packaging, and refactoring work
  MUST NOT change authored prompts, starter snapshots, private assertions,
  reference solutions, validation matrices, scoring weights, or pass criteria.
- A task-semantic change requires an explicit benchmark-authoring request,
  catalog/version review, updated public documentation, and two-way validation:
  the known-broken base must fail for the intended reason and the gold/reference
  implementation must pass every required assertion.
- Maintenance agents MAY inspect private assertions, gold patches, validation
  data, or prior results only when the explicit maintenance task requires it.
  They MUST NEVER copy or expose that material to an anonymous attempt or
  model-under-test workspace.
- Benchmark roots are read-only inputs during normal Hub operation. Generated
  public manifests, attempts, workspaces, caches, and logs belong under Rhenium
  state, never under `benchmarks/`.

The following Isaac PR2 baseline is explicitly frozen:

```text
benchmarks/isaac-core/exams/isaac-exodus-release-regressions.md
benchmarks/isaac-core/private/harbor/isaac-exodus-release-regressions/environment/exodus/
benchmarks/isaac-core/private/harbor/isaac-exodus-release-regressions/tests/
benchmarks/isaac-core/private/harbor/isaac-exodus-release-regressions/solution/
benchmarks/isaac-core/private/harbor/isaac-exodus-release-regressions/validation/
```

Its aggregate checksum is
`9a50aba82fc81b9df13075280a8323bd30484c6f6f35bc1520c5a613632913ef`.
An agent MUST NOT edit these paths or update the checksum test unless the user
explicitly requests a new Isaac benchmark baseline and authorizes revalidation.
Changing the expected checksum to accept accidental edits is prohibited.

Isaac version 0.6 currently returns `RuntimeActionRequired` for the official
Steam-client bootstrap when client state is absent. It does not launch the client
or expose noVNC. Agents MUST preserve that truthful behavior/documentation unless
they implement and validate the complete replacement flow.

## 6. Database, API, and compatibility rules

- Persistent schema changes MUST use an explicit version and a transactional,
  tested migration. Existing compatible task, run, job, attempt, model-setting,
  auth, runtime, and operation rows MUST NOT be silently discarded.
- Fresh-database and upgrade-path tests are both required for a schema change.
- Public models SHOULD reject unknown fields where the existing contract does.
- API errors MUST fail closed without stack traces, secrets, private paths, or
  hidden assertion content.
- Long-running auth/runtime actions MUST use operation records and expose
  only public challenge/action state.
- Cancellation MUST NOT be documented as immediate process termination until
  providers/builders actually implement cooperative interruption.
- Breaking CLI/API/plugin/schema changes require a major/minor version decision,
  and a `BREAKING CHANGE:` commit footer.

## 7. Dependencies, packaging, and generated files

- Python targets 3.12. New code MUST be typed and pass Ruff and Mypy under the
  repository configuration.
- Add dependencies only to the narrowest owning distribution. Engine/provider
  dependencies MUST NOT enter core.
- Dependency changes MUST update `uv.lock` deliberately and MUST NOT include
  unrelated lock churn.
- Frontend dependency changes MUST update `web/package-lock.json` deliberately.
- Shell entry points MUST use defensive quoting, avoid secret-bearing arguments,
  and pass `bash -n` plus ShellCheck.
- Build scripts MAY create output under ignored build/state locations, but those
  files MUST NOT be committed unless they are intentional source assets.
- Released helpers, proprietary images, and wheels MUST be built
  from reviewed source. Pinned hashes and version constants MUST match the actual
  immutable release assets.
- Licensing/provenance MUST be preserved. Do not copy third-party code or assets
  into the repository without compatible licensing and recorded provenance.

## 8. Documentation and support claims

An agent changing behavior MUST update the closest authoritative documentation:

- `README.md` for user-facing commands, support status, and navigation;
- `docs/plugin-contract.md` and `docs/adding-a-game.md` for extension contracts;
- `docs/managed-runtimes.md` for lifecycle, API, state, and security;
- `providers/steam/README.md` for Steam schema/protocol/helper releases;
- `web/README.md` for shadcn UI development;
- `docs/games/<game>.md` for an individual game's actual support matrix.

Documentation MUST describe implemented behavior, not intended future behavior.
If a path is unvalidated, manual, action-required, incomplete, or insecure by
design, say so directly. Do not use “managed”, “verified”, “supported”, “signed”,
“offline”, or “networkless” unless the implementation and evidence justify the
claim.

## 9. Required verification

Run targeted tests while developing. Before handing off a repository change, run
the full applicable checks from the repository root:

```sh
devenv shell -- ruff check src plugins providers tests
devenv shell -- mypy src plugins providers tests
devenv shell -- pytest -q
devenv shell -- npm run lint --prefix web
devenv shell -- npm run test --prefix web
devenv shell -- npm run build --prefix web
devenv shell -- shellcheck \
  run-benchmark scripts/prepare-exam scripts/score-exam \
  benchmarks/stardew-core/private/harbor/scripts/validate-task.sh \
  providers/steam/helper/build-helper.sh
git diff --check
```

Also run Bash syntax and ShellCheck over every Isaac shell script when those
assets or shared shell behavior are affected:

```sh
ISAAC_TASK=benchmarks/isaac-core/private/harbor/isaac-exodus-release-regressions
find "$ISAAC_TASK" -type f -name '*.sh' -exec bash -n {} \;
find "$ISAAC_TASK" -type f -name '*.sh' -print0 | xargs -0 shellcheck
```

Additional gates:

- A core-only change MUST verify core-only installation and no-plugin startup.
- A packaging change MUST build the affected wheels from a clean/ignored output
  directory and inspect required package data, including Web assets.
- A helper change MUST build/test every claimed RID and verify clean download
  hashes.
- A game-runtime/evaluator change MUST run its real engine-backed NOP and gold
  controls on a licensed controlled host. If that host is unavailable, the agent
  MUST report the engine validation as unrun; unit tests are not a substitute.

Engine-backed tests may skip only when the documented engine is genuinely
unavailable. The final handoff MUST list failed/skipped/unrun checks and distinguish
unit, emulated/container, and real-engine evidence.

## 10. Git and delivery rules

All commits MUST follow Conventional Commits 1.0.0:

```text
<type>(<optional-scope>)!: <imperative summary>
```

- Allowed types are `feat`, `fix`, `docs`, `refactor`, `test`, `build`, `ci`,
  `chore`, `perf`, `revert`.
- Use a short lowercase scope when useful, such as `core`, `hub`, `steam`,
  `isaac`, `stardew`, or `docs`.
- The summary is concise, imperative, and has no trailing period.
- Breaking changes use `!` and a `BREAKING CHANGE:` footer explaining migration.
- Each commit contains one coherent change and no unrelated formatting, generated
  output, local state, or user work.

An agent MUST inspect the final diff before committing. It MUST NOT amend, rebase,
force-push, create tags/releases, publish artifacts, or push commits unless the
user has requested that action or the established task workflow explicitly
authorizes it. Destructive actions require exact target resolution and explicit
confirmation where data loss is possible.

## 11. Definition of done

An agent may call repository work complete only when:

- the requested behavior is implemented at the correct architectural boundary;
- regression tests cover the important success and failure paths;
- relevant docs and support/security claims match the implementation;
- required checks pass, or every unavailable check is explicitly reported;
- no secret, licensed content, cache, generated state, or unrelated user change is
  present in the diff;
- `git diff --check` passes;
- the final response identifies material files changed, verification evidence,
  and any remaining limitation without overstating readiness.

## 12. Exam isolation rules

### Exam modes

- `strict` is the default. Solve without scorer feedback, run the scorer exactly
  once after implementation is complete, and do not edit the submission afterward.
- `practice` is allowed only when the user explicitly requests it. The agent may
  rerun the scorer and improve the submission from the report.
- Both modes use the same implementation requirements and evaluator. A practice
  result is not a comparable one-shot benchmark result.

`strict` is an integrity rule for the agent and operator, not an OS sandbox or a
scorer-enforced run counter. The operator must start the agent from the isolated
attempt directory and approve only the exact scoring command generated in
`PROMPT.md`.

### Honest exam boundary

When solving an exam, the agent MUST:

- read only the copied `EXAM.md`, this `AGENTS.md`, `CLAUDE.md`, `PROMPT.md`, and
  files created inside the attempt directory;
- work only inside the attempt directory and never modify the benchmark repository;
- avoid inspecting the repository named in `PROMPT.md`, including `benchmarks/`,
  `.rhenium/`, evaluators, hidden assertions, server suites, gold/reference files,
  validation data, runtime helpers, or prior submissions;
- implement required files only from the exam specification, supplied starter,
  printed API signatures, and documented game APIs;
- treat the scorer as opaque and never invoke private assertions, engine harnesses,
  or runtime helpers directly;
- avoid third-party implementations, upstream fixes, private assets, internet
  searches, and external code assistance for the exam solution.

### Scoring command

Run scoring only through the exact absolute wrapper command printed in
`PROMPT.md`. It has this shape and intentionally contains no task identifier:

```sh
"<clone-path>/scripts/score-exam" "$PWD"
```

For a native Windows attempt prepared with `scripts/prepare-exam.ps1`, the
approved command is instead:

```powershell
& "<clone-path>\scripts\score-exam.ps1" (Get-Location).Path
```

The default `full` profile runs every required assertion. DST requires its
headless dedicated server; GMod Addons requires the pinned native Windows App 4020
Dedicated Server and both Phase A/B processes; the GMod DarkRP and addon-repair packs
require the digest-pinned GLuaTest dedicated server in a networkless container; Palworld requires its pinned
native Linux dedicated server under UE4SS, acquired through the Steam provider by `rhenium runtime prepare`;
Stardew Valley requires the pinned real game and SMAPI
in a networkless container; Isaac requires the pinned native Afterbirth+ build
and all three networkless verifier processes. If the engine is unavailable, the
scorer reports an incomplete failure.

Use `--profile core` only when the user explicitly requests a reduced diagnostic.
A reduced result is incomplete and cannot pass an engine-backed plugin.

The scorer exits with status 0 only for a passing submission. After it finishes,
report:

- anonymous run ID and submission path;
- overall status and score;
- failed or skipped checks;
- whether every required engine-backed assertion ran;
- files created by the implementation.

In strict mode, the agent MUST NOT rerun the scorer, edit the submission after
scoring, alter benchmark files, or call hidden tools to improve the result.
