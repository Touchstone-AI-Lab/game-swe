# Balatro integration entry checkpoint

Maintainer: **Sangyu Pan**. The name is confirmed; no account or contact was inferred.

**Integration remains incomplete.** The entry/materialization/sealing layer is
implemented, but the native evaluator sidecar and runtime adapter have not been
activated or validated. No platform game was started. The licensed native Windows
maintenance decision in `RUNTIME-DECISION-REQUEST-v1.md` is pending.

## Implemented and checked

- Independent `rhenium-balatro-plugin` 0.2.0 distribution, registered through
  `rhenium.benchmarks`; schema-v2 `balatro/core` pack with all ten frozen tasks.
- Maintainer record, public-asset hash checks, exact-byte starter copying, identity-
  only anonymous contract/API presentation and absence of private/history assets
  from the attempt.
- Allowlisted, size-bounded starter sealing; immutable metadata and post-copy
  hashes checked; existing starter edits preserved as explicit conflicts.
- Result allowlist and sidecar response validator. Protocol tests cover identities,
  malformed/duplicate/oversize responses, nonfinite data, missing/duplicate checks,
  forged flags, mismatched fingerprints and incomplete cleanup. They use synthetic
  data, not a game or a fake engine pass.
- Installed-wheel CLI: `tasks` and `prepare-attempt` exit 0; `run-attempt --profile
  full` exits 1 with `runtime_action_required`, `complete=false`, `passed=false`.
  The submitted starter was sealed. This proves entry rejection at the runtime
  boundary, not base rejection for the task's intended behavioral defect.
- Real installed Balatro and contract distributions coexist. Tests exercise the
  same local task ID in two games, independent records, and a contract fixture
  pass while Balatro remains incomplete. Repeated Hub startup preserves the pack.

## Verification results

| Check | Result |
| --- | --- |
| Related platform regression | 135 passed, 0 failed/skipped; includes 43 Balatro tests |
| Earlier Balatro-only checkpoint | 41 passed before two extra projection tests |
| Ruff: `src plugins providers tests` | Passed, including final source |
| Balatro Mypy | Passed, 10 source/test files, with repository `src` on MYPYPATH |
| Full repository Mypy | Failed: 45 Windows/POSIX API errors in 10 unchanged files |
| Full `pytest -q` | Failed during collection: 7 authoring imports require `fcntl`; remainder not executed by that command |
| Web lint / test / build | Passed; 1 test file / 1 Web test |
| Wheel build and inspection | Core, Balatro and independent contract wheels built; required Web assets included; no game/dependency/private assets |
| Installed-wheel CLI | Prepared anonymous attempt; intentional incomplete full result |
| `git diff --check` and staged equivalent | Passed at check time; final recheck recorded in verification JSON |
| `devenv shell -- ...` | Unavailable on this host; direct installed-tool equivalents recorded instead |
| ShellCheck | Unavailable, not installed; required full command unrun |
| Isaac additional shell checks | Not applicable to this diff: no Isaac/shared shell changes |
| Native smoke / gold-base matrix / mutations | Unrun; runtime policy and native adapter pending |
| Cancellation/process cleanup through the sidecar | Unimplemented/unrun; synthetic cleanup-field rejection is not process-cleanup evidence |
| Disposable host / model calibration | Unimplemented / not performed |

The Mypy failures refer to `killpg`, `SIGKILL`, resource limits, POSIX file flags,
`fchmod`, `getuid/getgid` and `mkfifo` in existing core/provider/other-game files.
The collection errors are in `tools/authoring`, originating in its unconditional
`fcntl` import. They remain failed requirements; this report does not waive them
because they are outside Balatro. No shared implementation or unrelated test was
changed to suppress these failures.

## Preservation and evidence

The 76 pre-existing staged files and all 501 frozen PoC source files were checked
against their original records. The fixed dependency pin and protection-baseline
hashes are retained. A separate final read-only dependency/protection check is
recorded under the new local evidence directory. Original SWE-Game remains clean
at its original HEAD; no commit, push, PR, AGENTS change or host-setting change.

Source additions are confined to the independent staging repository. Root changes
are the new pytest test path and 12 lockfile lines registering the local plugin;
all previous dependency entries remain unchanged. Build output is ignored. Web
build removed `web/dist/.keep`; its original one-newline blob was restored exactly.

Local evidence is under `.test-state/balatro-integration-v1/`, including original
development failures, installation reports, source hashes, XML, CLI records and
wheels. It is operator-only, not part of the public task material or distribution.
The machine-readable checkpoint is `validation-entry-v1.json` next to this report.

Retained development failures: an initial test passed a string instead of the
required scorer Path; an oversized parameterized pytest ID exceeded Windows'
environment-variable limit; an initial CLI diagnostic used `list-tasks` instead
of the actual `tasks` command. These were corrected without changing task rules,
limits or pass criteria. The old files/logs were not overwritten.

## Remaining work and estimate

After an explicit runtime decision: bind pack-local private authored assets;
implement the fixed Python 3.13 sidecar, state-location adapter, reviewed candidate
authorization and owned-process cancellation; freeze and test; run a fresh bounded
pilot and the 60 gold/base workflows plus targeted controls through platform entry.
Resolve or obtain an authorized environment for the outstanding repository checks.

The initial estimate remains conditional: 10–16 hours effective work in total,
including an estimated 4–7 hours for serial engine validation. This checkpoint
completes only the entry layer. No completion time is promised while the runtime
decision and cross-platform verification route are unresolved.

See `REPLAY-entry-v1.md`. Historical PoC results remain historical: platform
engine-validated task count is **0**, not 10. This checkpoint creates neither an
eleventh task nor a model-calibrated or formally integrated release.
