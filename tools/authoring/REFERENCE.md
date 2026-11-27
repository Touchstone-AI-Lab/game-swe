# Authoring reference

Start with the [quickstart](README.md). This reference covers advanced operation,
compatibility, compiler feedback, and the clean-room integrity boundary.

`rhenium-authoring` is a repository-maintenance tool with two modes. The default
clean-room mode turns historical mod bug-fix evidence into newly implemented,
clean-room synthetic SWE-like tasks; it does not publish, modify, or ship the
upstream mod source. Generated tasks are labelled `clean-room synthetic`; this
process reduces copying and lookup leakage but is not a legal non-infringement
determination. The [project-history mode](#project-history-mode) instead vendors a
permissively licensed upstream repository at the parent of a landed fix, as the
hand-authored repository packs do.

## Credentials

Create the project-local ignored file `.rhenium/authoring-secrets.toml` from
`tools/authoring/authoring-secrets.example.toml`, fill the model, GitHub, and
CurseForge values, then set mode `0600`:
The secrets section is `[model]`; the old `[kimi]` name is still read as a
deprecated alias and warns on load.

```sh
mkdir -p .rhenium
cp tools/authoring/authoring-secrets.example.toml .rhenium/authoring-secrets.toml
chmod 600 .rhenium/authoring-secrets.toml
```

The CLI refuses symlinks, any other permission mode, missing values, and secret
files outside the current repository. Secrets are used only for outbound API
authentication and are excluded from prompts, errors, state records, and output.
Model-endpoint TLS verification defaults to `true`. A test service with a self-signed
certificate may set `verify_tls = false` in the ignored secret file, but this
weakens transport authentication and must not be used for production credentials.
`reasoning_effort` defaults to `low` and `max_tokens` to `16384`. The GitHub
token is optional; anonymous discovery works with GitHub's lower public rate
limit. CurseForge is skipped with an explicit warning when other sources are
available and its key is absent; a CurseForge-only run still fails closed.

For a gateway configured with `ANTHROPIC_BASE_URL` and `ANTHROPIC_AUTH_TOKEN`,
set `[model].protocol = "anthropic"`, use that base URL, and put the token in
`api_key`. The client posts to `/v1/messages`, with a top-level system prompt,
Bearer authentication, and the Anthropic version header. Only completed text
responses are parsed. The model is selected by `[model].model`; client-specific
model alias environment variables do not change this tool's configuration.
An optional `[model].review_api_key` uses a second credential for independent review;
the reviewer retains the same endpoint, protocol, model, and request settings.

## Workflow

Start a review batch:

```sh
devenv shell -- rhenium-author run \
  --mode review \
  --sources github,modrinth,curseforge \
  --games dst,stardew-valley,isaac-rebirth,garrys-mod,minecraft \
  --limit 20
```

To exercise task generation independently of crawling, provide a private JSON
array conforming to `HistoricalFix` (two to 100 entries) and run:

```sh
devenv shell -- rhenium-author model-check
devenv shell -- rhenium-author generate --input .rhenium/my-fixes.json --mode review
```

The input may include `issue_text`, `patch`, `changed_files`, and optional
`base_files`/`fixed_files`; it stays in ignored project state and is never
published verbatim.
Every run persists this input as a mode-`0600` private snapshot before calling
the model service. If it fails, fix the external issue and run
`devenv shell -- rhenium-author retry <failed-run-id>` without crawling again.
Successful model stages also save private mode-`0600` JSON under that run's
`checkpoints/` directory before downstream gates. These snapshots support failure
diagnosis; `retry` currently repeats generation from the saved source input.

The authoring state database uses schema version 2. On opening a version-1
database, the tool transactionally migrates existing rows and keys candidate
records by both run ID and candidate ID. Repeating the same candidate in a retry
therefore preserves the earlier run's record. Stop running authoring commands
before updating the tool; older tool versions cannot open the migrated database.

`--mode yolo` follows the same gates and automatically publishes each candidate
that passes independent review and complete two-way real-engine validation. It
does not commit or push. A failed candidate remains private and does not block
other candidates.

Inspect and manage review runs with:

```sh
devenv shell -- rhenium-author status <run-id>
devenv shell -- rhenium-author review approve <run-id> <candidate-id>
devenv shell -- rhenium-author review reject <run-id> <candidate-id> --reason "..."
devenv shell -- rhenium-author publish <run-id>
devenv shell -- rhenium-author export <run-id>
```

## Runtime preparation

Managed runtime acquisition and preparation remain explicit operator actions.

### One-command engine flow

`rhenium-author run ... --engine-account <alias> [--target N]` makes the
whole flow one command: `--engine-account` is the explicit operator request
to prepare each candidate's not-ready synth runtime inside that candidate's
isolated validation Hub before evaluating, so engine validation and the
engine-feedback repair happen inside `run` itself. Preparation copies the
operator Hub's `state.sqlite` (auth sessions) into the isolated state — the
database stays separate so staged catalog loading cannot archive operator
tasks — and reuses the operator acquisition cache so licensed depots are not
re-downloaded per candidate. It never logs in: a missing or expired provider
session still ends as `action_required` for the operator. `--target N` keeps
working until N candidates pass complete engine validation: it raises the
harvest limit to at least `4*N` (composition groups up to seven capsules per
candidate) and gives each rejected candidate one full regeneration attempt
(prior attempts' checkpoints rotate to `<candidate>-attemptK/`). `resume`
accepts `--engine-account` the same way. Without `--engine-account` the
manual flow below is unchanged.

### Manual preparation

When a run becomes `action_required`, locate its staged pack below
`.rhenium/authoring/runs/<run-id>/validation-packs/<candidate-id>/`, prepare the
reported synth runtime with that directory as `RHENIUM_BENCHMARK_PATH`. Validation
uses a separate Hub under
`.rhenium/authoring/runs/<run-id>/validation-state/<candidate-id>/`; explicitly set
`RHENIUM_STATE_DIR` to that path, `RHENIUM_DATABASE_URL` to its `state.sqlite`
SQLite URL, and `RHENIUM_CACHE_DIR` to its `cache/` when preparing that runtime.
This prevents staged catalog loading from archiving the operator's normal Hub
tasks. After preparation, run:

```sh
devenv shell -- rhenium-author resume <run-id>
```

The synth runtime IDs are:

| Game | Runtime |
| --- | --- |
| Stardew Valley | `stardew-valley/stardew-1.6.15-smapi-4.1.10-synth` |
| Garry's Mod | `garrys-mod/gmod-gluatest-synth` |
| Isaac | `isaac-rebirth/afterbirth-plus-1.06.t1-synth` |
| Minecraft | `minecraft/paper-1.21.11-132-synth` |
| DST | Uses the configured dedicated server; no managed runtime record |

A Minecraft synth pack, whether staged for validation or published to
`benchmarks/minecraft-synth`, carries its own copy of the pinned `private/runtime`
and `private/harbor/harness` trees from `minecraft-core`, because the plugin's
runtime builder builds the Paper base image and one verifier image per task from
the pack root. Preparing the synth runtime downloads the same pinned Paper jar
through the `official-download` provider, whose empty session is copied from the
operator Hub with the other auth sessions. It also needs the operator's own
acceptance of the Minecraft EULA, which is recorded per Hub and per pack (see
[docs/games/minecraft.md](../../docs/games/minecraft.md#runtime-setup)). An isolated
validation Hub therefore starts without it: the first preparation stops at
`action_required` (`accept-eula`), and the operator writes `eula=true` to
`.rhenium/authoring/runs/<run-id>/validation-state/<candidate-id>/packs/minecraft/synth/eula.txt`
before resuming. The authoring tool never writes that record.
The benchmark registers no `minecraft/synth` pack; a clean-room Minecraft
publication (`rhenium-author publish`, or a `--mode yolo` `run` or `generate`) creates
the directory.

### Native macOS Stardew diagnostics

An installed macOS Stardew 1.6.15 can be used for native **maintenance diagnostics**
without downloading the Linux depot. Explicitly run `rhenium-author macos-prepare
<run-id> <candidate-id> --game-dir /path/to/Stardew\ Valley`, then
`rhenium-author macos-check <run-id> <candidate-id>`. These commands require the
optional Stardew and local-files distributions, Docker for compilation, a logged-in
macOS desktop, `sandbox-exec`, and x86_64 execution. Preparation copies the installation
to isolated project state and never installs into the user's game or touches saves.

This profile executes the generated C# suite, not arbitrary Linux shell setup/gates.
Reports, copies, and logs stay in `runs/<run-id>/macos-diagnostics/<candidate-id>`.
`macos-check` exits 2 and never updates the normal review/validation state, approves,
exports, or publishes. Read the `runtime.engineComplete` and assertion counts for
each control; a native diagnostic is not a comparable `full` pass. See the
[runtime and security boundary](../../docs/games/stardew-valley.md#macos-native-maintenance-diagnostics).

## Integrity boundary

### Compiler feedback and regeneration

For new Stardew generations the model authors only `tests/TaskSuite.cs` plus case metadata.
The tool renders `tests/test.sh` from a checked-in trusted template: build/deploy,
timeouts, exact case-name/count verification, and reward writing are not model-authored.
The finished bundle still contains both files and remains compatible with the plugin.

Garry's Mod generations work the same way: the model authors only the GLuaTest file
`tests/suite.lua` plus case metadata, and the tool renders `tests/test.sh` from the reviewed
DarkRP runner with only the shell-quoted expected case names replaced. Staging, the audit
nonce, the patched result collector and reward writing are not model-authored. Earlier runs
asked the model for the shell runner without describing this flow, and every candidate was
rejected for a missing `EXPECTED=<count>` declaration.

Minecraft generations follow the same division: the model authors only
`tests/TaskSuite.java` (one `public final class TaskSuite implements GcbSuite`
with one `@GcbCase("<case id>")` method per `case_ids` entry) plus case metadata.
The tool statically checks that the `@GcbCase` names equal `case_ids` as a
multiset and that neither the suite nor the implementation references
`net.minecraft.*`, `org.bukkit.craftbukkit`, `System.exit`, `Bukkit.shutdown`
or `Runtime.halt/exit`, then renders `tests/test.sh` from
`assets/minecraft-test.sh.in`: the shell-quoted expected case names, a
cross-check that the frozen `tests/task.json` declares exactly those
`serverCases` with no `unitCases` and the `javac` build, and the reviewed
minecraft-core harness flow (`python3 /tests/verify.py`, reward fail-closed).
The publisher writes `tests/task.json` in the plugin's `task_manifest()` shape,
renders the agent and verifier Dockerfiles from the harness templates (no
dependency warm-up; the verifier image is `FROM
gcb-minecraft-paper-verifier:1.21.11-132` and copies `TaskSuite.java`), mirrors
the starter into `tests/starter`, copies `verify.py` and `solution/solve.sh`,
and keeps a reference copy of the trusted `javac-build.sh` under `scripts/`.
None of these paths may appear in a model-authored verifier.

#### Minecraft generation contract

Generated Paper plugins are Java 21 sources below `src/main/java/` plus the
frozen `src/main/resources/plugin.yml` — no Gradle, Maven, wrapper, `src/test`
or other build file is accepted, because the trusted build is
`javac --release 21 -proc:none` against the pinned Paper 1.21.11 (build 132)
server classpath followed by `jar`. Only `org.bukkit`, `io.papermc.paper`,
`net.kyori.adventure` and the JDK may be referenced; `plugin.yml` must declare
`name` equal to `loader_identity`, a `main` class that exists in
`src/main/java`, `api-version: '1.21'`, and none of
`depend`/`softdepend`/`libraries`/`load` (the interface contract validator
enforces this, and `return-value` entry points may not be `void`). Every
behavior needs an observable entry point without players: a console command
with deterministic reply text, an event the verifier can construct and call
through `GcbEvents.call`, a scheduler task with a stated delay, configuration,
or a public non-void method reached through
`Bukkit.getPluginManager().getPlugin(loader_identity)` and reflection. The
suite is compiled without the submission on its classpath, so it can never
import the generated package. Minecraft is an exact-case game: the evaluator
emits per-case `caseOutcomes`, and control audits compare failed case
identities as well as counts.

#### Minecraft javac preflight

`tools/authoring/checks/minecraft-project-check` and
`tools/authoring/checks/minecraft-verifier-check` (Python standard library,
sharing `_javac_check.py`) implement the check-command contract below for
Minecraft: the project check compiles the generated tree and confirms the
`plugin.yml` `main` class was produced; the verifier check compiles
`tests/TaskSuite.java` against the server classpath plus the GcbHarness jar
only. They take the classpath from:

| Variable | Meaning |
| --- | --- |
| `RHENIUM_MINECRAFT_CLASSPATH` | A directory (every `*.jar` below it, or a directory of classes) or a colon-separated list of jars/directories. |
| `RHENIUM_MINECRAFT_CLASSPATH_IMAGE` | A prepared verifier image; its `/opt/gcb/classpath.txt` jars and `/opt/gcb/harness/gcb-harness.jar` are copied out once with `docker cp` into `.rhenium/authoring/minecraft-classpath/<hash>/` and reused. |
| `RHENIUM_MINECRAFT_HARNESS_CLASSPATH` | The GcbHarness jar (or a colon list) for the verifier check; defaults to the image cache copy or a `gcb-harness.jar` found on the classpath. |
| `RHENIUM_MINECRAFT_CLASSPATH_CACHE` | Overrides the image cache directory. |
| `JAVA_HOME` | Selects the JDK whose `javac` is used; otherwise `javac` from `PATH`. |

Missing `javac`, a missing classpath, or a missing harness jar make the check
incomplete (`complete: false`, exit 1) and the tool stops; they are never
reported as clean. `JAVA_HOME` and every `RHENIUM_MINECRAFT_*` variable are the
only additions to the child environment; model credentials are never forwarded.

`run`, `generate`, and `retry` accept `--verifier-check-command /absolute/path/to/checker`
and `--project-check-command /absolute/path/to/project-checker`. The latter checks
the fixed implementation, combined broken base, and every single-defect project;
compile errors trigger up to three generations at the owning role. The fixed-code
role receives only its own prior output and compiler findings, never the verifier
or upstream implementation. Omitting either optional check does not waive the
mandatory full engine validation.
This is a trusted operator executable, never a model-selected command. It receives
JSON on stdin (`schema_version: 1`, `files`) and must return only JSON on stdout:
`{"schema_version":1,"complete":true,"findings":[]}`. Compiler errors belong in
`findings`; unavailable infrastructure must set `complete` to false or exit nonzero.
The tool stops if a configured compiler service cannot complete. Model credentials are
not passed through the child environment; SSH agent access is retained for an
explicitly configured remote checker.

Up to three verifier generations are attempted with compiler findings and that
role's own previous output. The verifier never receives the independently generated
gold implementation. Requests/findings are kept in private project-local preflight
receipts. The Python API can also freeze `case_contract` during repair so no case
or capsule mapping is silently dropped. Compile success is only a preflight: full
base/gold and single-defect engine controls still gate acceptance and publication.
Repeated independent successful generations are measured evidence, not a promise
of a 100% future generation success rate.

### Engine-feedback repair

A candidate that fails complete two-way engine validation gets one bounded
repair round by default (`engine_repair_rounds`, settable to 0). The failed
`ValidationReport` receipts are routed to the role that owns the failure: a
failed gold control regenerates the fixed implementation, a control that ran a
different case set than declared regenerates the verifier with the case
contract frozen, and a wrong base/ablation failure identity regenerates the
defect injections. Feedback to the fixed implementer aggregates failures per
contracted entrypoint and never contains verifier case IDs, preserving the
information barrier; verifier and injector feedback may name the case IDs the
model itself authored. A repaired fixed implementation always gets freshly
injected defects. Every repair round re-runs the leakage gates and the
independent review, and repair artifacts are checkpointed with a `-repairN`
suffix. Any `unavailable` check (missing runtime) is operator work and never
triggers a model repair. `resume` runs the same bounded repair when the
model secrets are configured (repair artifacts checkpoint with a
`-resume-repairN` suffix, and `--verifier-check-command` /
`--project-check-command` apply to the repair generations); without
configured secrets it only re-validates. For restricted runtimes this is the
path where engine feedback actually reaches the model, because a fresh run's
isolated validation state always reports the runtime unavailable until the
operator prepares it. A candidate that still fails is rejected with a reason
noting the repair rounds spent.

### Thinking-model endpoints

For OpenAI-protocol thinking models only `message.content` is parsed; the
`reasoning_content` stream is never parsed or logged, and stage receipts carry
only sizes (`reasoning_characters`, `reasoning_tokens`, `completion_tokens`).
A response ending with `finish_reason: "length"` raises the per-request token
budget once (doubling `[model].max_tokens` up to 131072) before failing with a
budget hint, because a thinking model bills reasoning tokens from the same
`max_tokens` budget as the JSON answer. `reasoning_effort` (including `max`)
is sent to the endpoint verbatim; `rhenium-author model-check` is the probe
that shows whether the endpoint accepts it and reports the token receipts.

### Retry policy

Model connections use a 30-second connect/pool timeout and a 600-second response
timeout. Progress distinguishes response timeouts from connection/TLS errors
without exposing transport exception text or credentials.
Transport failures (HTTP 429/409/5xx, timeouts, TLS errors) have their own
attempt budget (5 by default) with exponential backoff 1→2→4→8→16 seconds plus
jitter; a `Retry-After` header up to 60 seconds takes precedence, and a 409
cold-start on a dedicated endpoint follows the same schedule. Invalid
structured responses retry immediately within the content attempt budget, and
HTTP 400/401/403/404 fail fast without retrying.

Stardew guidance records the pinned API facts: `SDate.Season` is an enum,
`Options.zoomLevel` is read-only, and `FarmHouse.getChildren()` returns a detached
list. Test fixtures mutate the home's `characters` collection and verify their own
setup before invoking the mod. The synthetic runtime creates an absolute XDG
configuration directory before SMAPI's first launch; it does not edit frozen packs.
The [pinned SMAPI SDate API](https://github.com/Pathoschild/SMAPI/blob/4.1.10/src/SMAPI/Utilities/SDate.cs)
uses `SDate.Now()` and throws `ArithmeticException` for dates before year one;
catching only the narrower `OverflowException` misses that boundary. Reflective
test calls unwrap invocation exceptions for useful failure diagnostics.
Reflection-based verifiers use non-generic `ModRegistry.GetApi(id)` after initialization;
`GetApi<object>()` is rejected because SMAPI requires an interface for the generic overload.
Stardew Valley, Left 4 Dead 2 and Minecraft control audits compare exact failed
case IDs as well as counts, so failing a sentinel cannot masquerade as the
intended isolated regression. Only those three evaluators emit per-case
`caseOutcomes` receipts; the other games are audited by complete/passed state
and assertion counts because their scorers do not produce case-identity
evidence. Every engine control check now records structured evidence in
`validation.json` (observed complete/passed state, assertion counts, and
expected versus observed failing case IDs — values the model itself authored,
never private assertion content). The engine log of every control
(`runtime_log`: build, server and verifier output) is also saved under
`candidates/<candidate-id>/engine-logs/<control>.log` with mode `0600`, because
the evaluator's temporary directory is gone once the receipt is returned.

The acquisition stage accepts only supported games, allowlisted SPDX licenses,
GitHub-backed source history, immutable base/fixed SHAs, and merged PRs whose
title or body has repair semantics and whose files expose usable patches.
Bot and draft PRs are rejected. Modrinth and CurseForge are discovery sources;
their candidates must resolve to an eligible GitHub repository. Downloaded
release binaries are not accepted as clean-room evidence. Each game's runtime
language is fixed (`.lua` for DST, Isaac and Garry's Mod, `.cs` for Stardew,
`.java` for Minecraft; Kotlin plugins are not harvested), and a landed change
that also edits another language (native code, or another game's language) is
skipped as loader or engine work. For Minecraft, a repository is mined only
when its default branch holds `src/main/resources/plugin.yml` or
`src/main/resources/paper-plugin.yml`; Modrinth discovery uses the
`project_type:plugin` facet. Files below `build`, `buildSrc`, `gradle`,
`generated`, `target`, `test(s)`, `docs` and `.github` are never runtime source.
Acquisition scans up to three pages of merged PRs and excludes documentation,
deployment, test and non-runtime files. It records the landed commit and its
first parent with matching code context. Seeded `generate` and `retry` inputs
also require a runtime implementation change and an allowed license. This is a
minimum eligibility check; the model review still has to confirm gameplay scope.

Only the behavior extractor and independent reviewer see historical issue text
and patches. After extraction, an isolated interface-design request receives only
the behavior capsules and trusted game guidance. It specifies the synthetic
project's public files, exact loader identity and serialized metadata, module/load
identifiers, entrypoint signatures, typed inputs, exact return schemas, observation
channels, and per-capsule entrypoint mapping. The fixed project
and verifier are generated independently from that same public interface contract;
the defect injector and prompt author receive it too. Neither implementer nor
verifier sees the other's source. New staged bundles retain the shared contract;
older unversioned staged contracts remain readable through a legacy model; new
generation requires contract schema version 2. Exact load metadata must agree in
fixed, base and every ablation. An independent model request
compares the private evidence with the output. Deterministic gates reject source
identity terms, unsafe paths, oversized output, and copied normalized 50-token
sequences. Identity matching uses token boundaries and excludes conventional
source directories and mod entrypoint filenames only when they occur in upstream
file paths; repository identities and distinctive path names remain checked.
JVM layout words (`src/main/java`, `resources`, `plugin`, `listener`, `command`,
`bukkit`, `paper`, `plugin.yml`, `build.gradle.kts`, `pom.xml`, `Main.java`),
Java keywords and the public Bukkit/Paper/Adventure vocabulary
(`JavaPlugin`, `CommandSender`, `EventHandler`, ...) are generic for Minecraft
sources; the social-handle pattern exempts Java annotations (`@Override`,
`@GcbCase`) and Javadoc block tags while still rejecting lowercase `@handles`.
Trusted verifier guidance specifies the existing DST sandbox/server interfaces and
Stardew `IGcbSuite` harness, including their case formats and real-engine launch
requirements. New Stardew interfaces include a root-level solution, project,
manifest, and build properties; generated paths are relative to the mod root.
The Stardew generation contract uses local game/MonoGame references, flat build
output with its exact manifest, and requires every behavior to have a registered
live game trigger using the same public API returned by `Mod.GetApi()`. Verifiers
retrieve that API using the shared manifest ID and observe the declared public
method results. These instructions still require real-engine validation; generated
projects are not supported merely because they match the requested file layout.

Every composite contains two to seven defects. Before publication, Rhenium runs
static Bash syntax and ShellCheck checks on generated verifier shell scripts,
passing their text through stdin without executing it. Missing checkers, invalid
syntax, lint findings, and checker override directives reject the candidate;
diagnostics expose only relative script names, line numbers, and check codes.
These checks do not establish engine readiness. For engine verification, Rhenium runs
the combined base, fixed gold, and one fixed-plus-single-defect ablation per
defect through the selected plugin's `full` profile. Every run must complete;
base and ablations must fail, and gold must pass. Missing engines, runtimes,
assertions, or trustworthy result evidence fail closed.

Validated generated packs use Apache-2.0 and are written to separate `synth`
packs. Private source provenance records URLs, immutable SHAs, SPDX identifiers,
and patch hashes, but not source or patch content. Training exports live only
under `.rhenium/authoring/exports/` and are never committed automatically.

### Fresh material across runs

`rhenium-author run --exclude-used-fixes` skips every historical fix that an
earlier run under `.rhenium/authoring/runs/*/historical-fixes.json` already
used (identity: repository URL plus fixed commit), so consecutive harvests of
the same sources draw fresh material instead of regenerating the same
behaviors. A fix whose changed-file context exceeds 512 KiB is skipped during
harvesting rather than aborting the run.
`--per-repository N` caps the fixes harvested from any one repository so a
prolific project cannot dominate every composite candidate.

## Project-history mode

`rhenium-author history run` authors repository tasks in the
`benchmarks/minecraft-core` format from real project history. It is implemented
for Minecraft (Paper plugins) only. The upstream tree at a landed fix's first
parent is the starter, the fix's main-source changes are the reference
(`solution/after`), the repository's own build and JUnit tests are frozen, and
the model writes only the public exam and the hidden live-server suite.
Publication writes accepted tasks to `benchmarks/minecraft-history` (pack id
`history`, catalog `rhenium-minecraft-history-v1`, runtime
`paper-1.21.11-132-history`), creating the pack when it is absent. The benchmark
registers no `minecraft/history` pack.

```sh
devenv shell -- rhenium auth login official-download
devenv shell -- rhenium-author history run --engine-account default --target 5 --workers 2
devenv shell -- rhenium-author history run --repository owner/name --per-repository 5
devenv shell -- rhenium-author history run --include-published --fix owner/name@<sha>
devenv shell -- rhenium-author history resume <run-id> <candidate-id>...
devenv shell -- rhenium-author history publish <run-id> <candidate-id>...
```

`history resume` reruns candidates from their engine controls with every model
checkpoint (triage, authored task, review) reused, for example after a runtime
preparation failure; `--from-review` reviews (and if needed revises) the
authored task again first. Runtime preparation is serialised by a file lock under
`.rhenium/authoring/locks/`, because every candidate prepares the same runtime
in its own isolated Hub.

Each candidate's isolated Hub also needs the operator's own Minecraft EULA
acceptance, which the tool never writes. Until it exists, that candidate stops with
`runtime preparation needs an operator step` and the path to write:
`.rhenium/authoring/runs/<run-id>/candidates/<candidate-id>/validation-state/packs/minecraft/history/eula.txt`.
After writing `eula=true` there, run `history resume` for the candidate.

Stages, each checkpointed under `.rhenium/authoring/runs/<run>/candidates/<id>/`:

1. **Walk.** Repositories come from GitHub search (or `--repository`). One
   recursive git-tree request keeps only Java Paper/Bukkit plugin layouts,
   including multi-module ones. Each repository's closed pull requests (REST
   list, not search) and default-branch commits are read page by page; the
   `history_cursors` table (authoring schema 3) makes the next run continue
   further back instead of re-reading the same pages. A fix is kept only if it
   is described as a fix, is not by a bot, changes plugin Java sources by at
   most 150 lines, touches no frozen build file and no foreign-language code.
   Fixes already used by an earlier run, or vendored by `minecraft-core` or (when
   it exists) `minecraft-history`, are skipped unless `--include-published` is given.
2. **Checkout and build probe (no model).** The base and fixed commits are
   downloaded as GitHub tarballs into `.rhenium/authoring/repos/` and unpacked
   without links, CI/IDE folders, build output or non-wrapper archives. The
   build (Gradle with a committed wrapper, or Maven with a wrapper or the pinned
   3.9.11 release) is inferred from the repository and proven by building the
   real agent image with the exact warm-up commands of `materialize.py`, then
   rebuilding the reference offline on top of that cache. Every upstream JUnit
   test must pass on both; their identities become `unit_cases`. Paperweight,
   Kotlin, Gradle without a wrapper, missing licence files, and fixes that
   delete a source file are rejected here.
3. **Triage.** A read-only repository agent (tools: `list_dir`, `read_file`,
   `grep`, `show_fix`, bounded turns, elided old observations) decides whether
   the fixed behaviour can be driven and observed on a headless server without
   players.
4. **Author.** The same kind of agent writes the exam (Context, Symptom, Task,
   Evaluation), the GcbHarness suite, optional plugin seed data and the case
   contracts. The exam describes what goes wrong and what must happen, never
   why: no cause, faulty method, fault count or repair. A read-only `examples`
   tree gives the author the GcbHarness API source, maintainer lessons
   (`history/assets/harness-notes.md`: output capture for Adventure-based
   plugins, asynchronous commands, start-up defects graded through reload) and
   the hand-written `minecraft-core` suites of *other* repositories; suites of
   the candidate's own repository are never shown. Inside its loop every answer is checked for case/annotation
   agreement and forbidden calls, compiled with `javac` in the local
   `gcb-minecraft-paper-verifier` image against Paper, the harness and the
   built base plugin jar, and passed through an exam leakage gate (no URLs,
   hashes, issue numbers, upstream wording or diff stretches).
5. **Review.** An independent reviewer (the `review_api_key` credential when
   set) must approve that every target case is derivable from the exam, that no
   case relies on an unpublished convention and that the exam does not diagnose
   the defect; one revision is allowed. A task changed by the engine repair loop
   is reviewed again before it counts.
6. **Engine controls** on the real server in an isolated Hub: the starter must
   fail exactly the target cases; the reference must pass three times; an
   alternative written from the exam alone, without the fix, must pass (a saved
   alternative is reused on resume only for the same exam text); a
   target-negative must fail only target cases (one reverted hunk of the fix,
   or, when no single hunk compiles and is observable, a model-written partial
   repair of the reference); a tampered reference
   (broken build files, one upstream test deleted) must still pass. A
   model-written compat-negative that keeps every target but breaks a preserved
   case is recorded when one is found. Failures of the starter or reference go
   back to the author with case results and the server log tail.
7. **Publication** (`--mode yolo`, or `history publish` after review) writes the
   canonical inputs, runs the pack's own `materialize.py`, and writes
   `private/study-controls/<id>/` (manifest, patches, alternative tree, draft
   clause map) so the task can go through `rhenium-study e0` unchanged.

The repository agent accepts one JSON action per turn. Thinking endpoints that
answer with their native tool-call markup instead (DeepSeek's DSML invocations,
alone or mixed with JSON) are translated into the same action; the last fifth of
the turn budget is reserved for answering, so a rejected answer can still be
corrected. Setting `RHENIUM_AUTHORING_DEBUG_DIR` makes the model client save
every answer it cannot parse (mode 0600) for diagnosis; unset, no model text is
written anywhere.

Network use is limited to authoring: GitHub (API and tarballs), Maven/Gradle
repositories while probe images warm their caches, and the model endpoint.
Agent tools read only local checkouts, and every engine control runs with no
network.
