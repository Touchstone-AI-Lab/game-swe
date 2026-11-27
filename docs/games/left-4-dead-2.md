# Left 4 Dead 2 support

| Field | Value |
| --- | --- |
| Plugin ID | `left-4-dead-2` |
| Status | `In Development` |
| Maintainers | Zhuoran, PrinsYin |
| Game runtime | Anonymous dedicated-server App `222860`, build `23990100` |
| Extension runtime | MetaMod:Source `1.12.0-git1225`; SourceMod `1.12.0-git7246` |
| Submission languages | SourcePawn and Squirrel |
| Evaluator | Python/Bash plus offline real-server assertions in Linux x86_64 containers |

The `left-4-dead-2/core` pack contains ten source-only repository-debugging
tasks covering five independently licensed mod repositories. The public
workspace contains the broken source tree and authored symptom report. Private
tests, validation contracts, reference repairs, and the dedicated server are
not materialized into the agent workspace.

Full evaluation uses task-specific verifier images derived from a shared,
build-asserted runtime. The verifier runs with networking disabled and requires
the exact frozen case set before it can report a complete result. No Valve game
files or prepared images are committed.

The trusted verifier owns `/logs` and `/logs/verifier` with mode `0700` inside
each disposable container. Game processes run as the separate `steam` user and
cannot replace these result files. Reports are copied out after execution; host
log directories are not mounted writable into the container. Cleanup targets
only the container created by that run, including after timeouts. Report reads
reject escaping paths, symlinks, and oversized files. Complete results expose
per-case outcomes for control audits and reject explicit environment failures.
The trusted controller retains `CAP_KILL` to stop its own downgraded `steam`
process groups inside the container's private PID namespace. Without that
capability, the frozen harness's `killpg` cleanup fails with `EPERM`; the game
itself still runs without those root controller capabilities.
Bounded tails of the real-server logs are retained with the verifier summary for
diagnosis; only the complete trusted verifier report supplies scoring outcomes.
Runtime archive downloads use bounded HTTP/1.1 retries for interrupted transfers;
TLS verification and every pinned archive SHA-256 remain mandatory.
SteamCMD bootstrap is cached separately. Cold-client installation requests retry
at most three times per platform (Windows content, then Linux binaries), and
preparation still requires the exact server build and executable after download.
The pinned SourceMod archive uses the official GitHub release tag
[`1.12.0.7246`](https://github.com/alliedmodders/sourcemod/releases/tag/1.12.0.7246);
its asset filename retains `1.12.0-git7246`. Mixing those formats produces a 404;
correcting the URL does not change the selected build or archive checksum.
The official AlliedMods download mirror is tried first, with GitHub as a transport
fallback. Both paths must satisfy the same frozen archive SHA-256.
Failed Docker builds retain bounded diagnostics under the selected runtime cache's
`build-logs/` directory with mode `0600`. Their public failure messages omit
raw build output and the operator's private paths, including on build timeouts.

Prepare and verify the runtime through the Hub:

```sh
rhenium auth login container
rhenium runtime prepare left-4-dead-2/l4d2-23990100-sourcemod-1.12.7246
rhenium runtime verify left-4-dead-2/l4d2-23990100-sourcemod-1.12.7246
```

Recorded controls are documented in the
[pack README](../../benchmarks/l4d2-core/README.md). They characterize only
the frozen prompts, source snapshots, runtime, and run batches stated there.

## Harbor tasks

The `left-4-dead-2/core` pack adds ten SWE-style repository-debugging tasks over five large,
independently licensed L4D2 mod codebases. Agents receive source-only broken
repositories. Private verification recompiles SourcePawn submissions or packages
Squirrel VScripts, then exercises observable behavior in a real headless Left 4
Dead 2 dedicated server.

| difficulty | task | upstream shape | groups | private cases | local controls |
|---|---|---|---:|---:|---|
| easy | [`l4d2-competitive-release-regressions-easy`](../../benchmarks/l4d2-core/private/harbor/l4d2-competitive-release-regressions-easy/) | Competitive Rework gameplay/lifecycle plugins | 3 | 20 | [versioned review controls](../../benchmarks/l4d2-core/review-revisions.md) |
| medium | [`l4d2-left4dhooks-api-regressions-medium`](../../benchmarks/l4d2-core/private/harbor/l4d2-left4dhooks-api-regressions-medium/) | Left4DHooks native bridge and public ABI | 12 | 71 | [versioned review controls](../../benchmarks/l4d2-core/review-revisions.md) |
| medium | [`l4d2-infected-bots-release-regressions-medium`](../../benchmarks/l4d2-core/private/harbor/l4d2-infected-bots-release-regressions-medium/) | L4D Infected Bots capacity/config/timer/finale lifecycle | 4 | 18 | [versioned review controls](../../benchmarks/l4d2-core/review-revisions.md) |
| hard | [`l4d2-linge-release-regressions-hard-v3`](../../benchmarks/l4d2-core/private/harbor/l4d2-linge-release-regressions-hard-v3/) | LinGe HUD/cache/hint/reward release batch | 9 | 42 | broken 28/42; oracle 42/42; nine predicates; six alternatives 42/42 |
| hard | [`l4d2-mutant-tanks-release-regressions-hard`](../../benchmarks/l4d2-core/private/harbor/l4d2-mutant-tanks-release-regressions-hard/) | Mutant Tanks core/reward/ability release batch | 9 | 57 | [versioned review controls](../../benchmarks/l4d2-core/review-revisions.md) |
| hard | [`l4d2-linge-director-state-hard`](../../benchmarks/l4d2-core/private/harbor/l4d2-linge-director-state-hard/) | LinGe configuration, reentrant dispatch and Director ownership | 9 | 41 | oracle and alternative 41/41; report omission controls |
| hard | [`l4d2-competitive-score-lifecycle-hard`](../../benchmarks/l4d2-core/private/harbor/l4d2-competitive-score-lifecycle-hard/) | Competitive Rework score, ledge and half-round lifecycle | 7 | 57 | oracle and alternative 57/57; report omission controls |
| hard | [`l4d2-vslib-scheduler-persistence-hard`](../../benchmarks/l4d2-core/private/harbor/l4d2-vslib-scheduler-persistence-hard/) | VSLib scheduler and safe persistent data | 8 | 52 | [versioned review controls](../../benchmarks/l4d2-core/review-revisions.md) |
| hard | [`l4d2-confogl-cvar-transactions-hard`](../../benchmarks/l4d2-core/private/harbor/l4d2-confogl-cvar-transactions-hard/) | Confogl staged ConVar transactions and finite reentry | 7 | 42 | [versioned review controls](../../benchmarks/l4d2-core/review-revisions.md) |
| hard | [`l4d2-library-map-tank-state-hard`](../../benchmarks/l4d2-core/private/harbor/l4d2-library-map-tank-state-hard/) | L4D2Lib map snapshots and Tank encounter lifecycle | 8 | 44 | [versioned review controls](../../benchmarks/l4d2-core/review-revisions.md) |

The five additional hard tasks now have 236 cases, bringing the pack to 444.
The [review revision](../../benchmarks/l4d2-core/review-revisions.md) repairs integration
coverage and test fairness. The revised contracts have not been model-calibrated.
The `hard` labels remain author assessments, not measured solve-rate guarantees.
See the [production-code and task-identity review](../../benchmarks/l4d2-core/task-independence.md)
for different repair surfaces and shared-baseline split precautions.
The five hard additions were validated through the Hub full profile on one Linux host
after verifier-harness fixes ([record](../../benchmarks/l4d2-core/validation/hub-full-profile-hard-tasks.md)).

The former focused LinGe starter was removed because its behavior was fully
subsumed by hard-v3. The original five tasks differ in both codebase and defect surface:
ordinary gameplay integration; pointer/ABI/detour bridging; infected-bot
scheduling and configuration; a nine-group cross-subsystem Squirrel regression;
and Mutant Tanks core/ability integration. The five additions reuse LinGe and
Competitive Rework for different state, persistence, transaction and lifecycle
defects; each includes the relevant previously accepted fixes.

Each task has the standard Harbor layout used by the DarkRP, Isaac, and Stardew
branches:

```text
<task>/
  task.toml       metadata, provenance, resource and network policy
  instruction.md  public symptom report given to the agent
  environment/    Dockerfile and broken source tree
  tests/          private reward gate and real-engine behavior suite
  solution/       reference repair used by Harbor's oracle control
  validation/     case contracts, controls, and reviews
  NOTES.md        maintainer-facing design and reproduction notes
```

No Valve game files are committed. The managed runtime under
`benchmarks/l4d2-core/private/runtime/` builds the shared,
verifier-only runtime from anonymous SteamCMD app `222860`, pinned MetaMod and
SourceMod distributions, and a fail-closed L4D2 build-id assertion. Agent images do
not contain the game. Tests, validation records, and reference solutions are not
mounted in the agent workspace; trial networking is limited to the configured model
API endpoint. Prepare the shared verifier runtime with the commands above before
invoking these tasks. Harbor then builds the selected task's `tests/Dockerfile` as
a separate, offline verifier image. The agent image contains source and compiler
tooling but does not contain the game server or hidden tests.

## Controlled Lab validation

On 2026-09-06, the integration worktree based on PR #4 and current main was
prepared from the pinned source on the Lab Linux x86_64 host. After fixing runtime
download, controller permissions, and report collection, the original five `full` NOP/gold
control pairs completed with the exact frozen case-name sets:

| Task | Broken NOP cases passed | Reference cases passed |
| --- | ---: | ---: |
| Competitive Rework | 13/20 | 20/20 |
| Left4DHooks | 30/72 | 72/72 |
| Infected Bots | 14/18 | 18/18 |
| LinGe hard-v3 | 28/42 | 42/42 |
| Mutant Tanks | 32/57 | 57/57 |

This is ten complete full-profile runs and 418 case verdicts; all 209 reference
cases pass. NOP failures are expected negative controls, including fail-closed
groups in the authored broken implementations. Some cases labelled `guard` in
the frozen records also fail on those broken implementations; this is not a claim
that every NOP guard passes. The oracle, instructions, private assertions, source
snapshots, scoring, and recorded validation matrices were not modified.

The verified immutable runtime artifact identity is
`sha256:fde7052b0f2b72587eee75a5cd8ca1e25585f37aadd52c8ad8656a37be7f49b1`.
The source-level controls and per-run receipts are retained in restricted Lab
state; no Valve binaries, images, Steam sessions, or raw logs are published.
This evidence is for the controlled Linux host, not native macOS or Windows/WSL
engine support, and is not a fresh model-capability calibration.

## Additional hard-task authoring validation (historical 1.1.0)

The five additional hard tasks contribute 229 cases, bringing the catalogue to
ten tasks and 438 cases. Each has a full source snapshot, reference repair,
behavioral case mapping, omission controls, and a fresh independent review.
The original five frozen tasks remain intact.
No model calibration was requested or performed for the new authoring batch.

New controls run real dedicated servers inside offline Linux containers managed
from the local Windows worktree, using the existing pinned image
`sha256:3604481021c1b605741e994fb623834fb0725b2309e53b7ed9a4c86fe3fb65cd`.
These are direct maintainer control runs, not a new Hub full-profile experiment
or a claim of native Windows game-server support. Reference and alternative
implementations pass all new cases. See each task's `NOTES.md` and `validation/`
for exact hashes, negative controls, review decisions and coverage limitations.

## Review revision (pack 1.2.0)

The current pack contains 444 cases; 236 belong to the five additions. Seven
task contracts were versioned for fairness or regression-coverage corrections.
The historical tables above are not evidence for changed assertions. Current
NOP/reference, equivalent-implementation and targeted negative controls are
recorded in [review-revisions.md](../../benchmarks/l4d2-core/review-revisions.md).
These remain offline real Linux dedicated-server maintainer runs controlled
from Windows, not a claim of native Windows server support.

No model calibration has been run on the revised contracts.
The [task-identity audit](../../benchmarks/l4d2-core/task-independence.md) documents
actual production compile/load paths, distinct repair goals, and answer-bearing
shared baselines that must remain grouped across training/evaluation splits.
The Confogl suite explicitly records a surviving supplementary mutation;
passing reference controls do not establish exhaustive defect detection.

## Hub full-profile validation of the hard tasks (2026-09-24)

The five hard additions were first run through the Hub full profile
(`rhenium run left-4-dead-2/core/<task>`) on 2026-09-24, on one Linux x86_64 host
(Docker Engine 29.8.0, containerd overlayfs snapshotter on btrfs). There the
score-lifecycle reference failed 0/57 and several runs ended incomplete. Four
verifier-harness defects in the tasks' `tests/verify.py` were found: the first two
explain those results, and the other two appeared during the validation runs. All
four were fixed without changing any suite, case name, weight, pass criterion, exam,
starter or reference:

- SourceMod autoloads plugins in raw directory order. The score verifier created
  the score plugin before Left4DHooks, and this host's overlay lists new entries in
  creation order. The score plugin's `OnMapStart` therefore called a Left4DHooks
  native before Left4DHooks had started, and the SourceMod exception failed every
  suite closed. The verifier now stages plugins in their numbered load order. It
  reports `INVALID_ENVIRONMENT` (incomplete) if the directory would still list them
  in another order, which a hash-ordered filesystem such as ext4 may do; that case
  was not exercised.
- After SIGKILL, the five hard verifiers waited only five seconds for the server to
  be reaped. On a loaded host that took 8 to 15 seconds, and the verifier crashed
  with no case lines. They now wait up to 120 seconds and fail closed as
  `INVALID_ENVIRONMENT`.
- Each boot had 55 seconds of wall time to reach its FINAL marker. A healthy boot
  needs 5 to 15 seconds, but one L4D2Lib reference boot stalled during plugin loading
  for longer than that. The SourcePawn verifiers turn a missing FINAL into a failure
  of every case in that boot, so the reference failed. The five hard verifiers now
  allow 240 seconds. The Harbor `timeout_sec` metadata in `task.toml` is unchanged.
- The fail-closed `FAIL <case>:` message of the three SourcePawn hard verifiers
  quoted engine noise such as "Invalid counterterrorist spawnpoint". It now names the
  SourceMod exception or a missing FINAL marker. The message never changes a verdict.

After a re-prepare, every hard task's unchanged starter was complete and failed only
cases that pass with the reference: LinGe Director 11/41, score lifecycle 17/57,
VSLib 15/52, Confogl 0/42 and L4D2Lib 0/44. The Confogl and L4D2Lib starters fail
closed, so those two tasks have no preserved baseline. Each reference passed every
case three times with identical outcomes. E0 study controls for the five tasks are in
`benchmarks/l4d2-core/private/study-controls/`. Every target-negative, compat-negative
and alternative behaved as declared. The alternatives are reference-derived variants
from the pack's `validation/candidates.py`.

On the final images, the Competitive Rework easy task (13/20, 20/20) and LinGe
hard-v3 (28/42, 42/42) reproduced their recorded starter/reference results. The other
three original tasks were not re-run on them. The original verifiers still have the
five-second reap wait and 35 to 55 second FINAL budgets. On an intermediate image
build, the Infected Bots starter ended incomplete three times because of the reap
wait. On a loaded host those tasks can therefore end incomplete; they were not
changed here. Every prepare gives all ten images new IDs, because BuildKit
attestations differ per build; the filesystem layers were unchanged. Run ids, image
IDs and per-control outcomes are in the
[Hub validation record](../../benchmarks/l4d2-core/validation/hub-full-profile-hard-tasks.md).
This is evidence for this Linux host only. It is not native Windows, WSL2 or macOS
runner evidence, and it is not a model calibration.
