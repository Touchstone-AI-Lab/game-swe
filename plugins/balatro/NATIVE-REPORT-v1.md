# Native honest maintenance adapter v1

Status: **approved native honest-maintenance matrix passed; whole-repository gates remain incomplete**.
Maintainer: Sangyu Pan. Scoped authorization: `RUNTIME-APPROVAL-v1.md`.

## Implemented boundary

Balatro plugin 0.2.1 is independently packaged for Python 3.12 and registered through
`rhenium.benchmarks`. It uses a prepared Python 3.13 sidecar to call the existing
frozen Session/runtime/RPC. It adapts generated-state paths and result transport;
all ten frozen task contracts, candidates, scenarios and required assertions stay
byte-identical. No core execution/RPC logic or AGENTS.md is changed.

Submissions are anonymous public starters sealed below platform state. Only the
approved source-reviewed maintenance hashes can launch. Fingerprints separately
bind environment, original harness, task, candidate and new platform adapter.
Response identity, full required cases, original normal cleanup and protection
checks are independently rechecked before an anonymous result is projected.

Private authored assets are pack-local. No fixture repairs candidate behavior,
no scoring action is retried, no RPC deadline is increased, and restore continues
to use the established initialized seeded-run entry. Blank MENU load remains
outside scope. The sidecar receives only a constructed minimal environment.

Owned Windows Job Objects provide descendant cleanup, with a stdin gate before
request execution. They are not an untrusted-code sandbox. There is no licensed
acquisition, Steam login, system mutation, arbitrary submission support, model
experiment or disposable evaluation-host implementation.

## Final result

The installed platform entry completed **74 clean workflows / 208 native game
processes / 3,434 required check outcomes**. Every workflow completed; all controls
matched their declared outcomes. These are maintenance controls, not model trials.

- Ten tasks: gold passed all required checks three times each; base completed and
  was rejected for the declared semantic defect three times each. The 60 workflows
  ran interleaved, with new anonymous attempts and fresh native processes.
- Ten targeted mutations completed the same full task suites and were rejected.
- Four alternate correct implementations completed and passed the same suites.
- All 208 game processes exited normally, with no forced cleanup, reused run ID,
  residual owned process, protection drift or fixed-dependency mismatch.
- All ten base controls were checked byte-for-byte against their public starters.
  They therefore also cover unchanged-starter/NOP submission behavior.

| Task | Authored difficulty | Gold complete passes | Base complete rejections | Targeted wrong control | Correct alternative |
| --- | --- | ---: | ---: | --- | --- |
| growth-v2 | easy | 3 | 3 | M03-per-hand rejected | alternative passed |
| reversible-hand-limit-v1 | easy | 3 | 3 | M02-no-remove rejected | Not included |
| seeded-effect-stream-v1 | easy | 3 | 3 | M03-score-advances rejected | Not included |
| bounded-generator-v2 | medium | 3 | 3 | M02-fixed-release rejected | Not included |
| deck-removal-consistency-v2 | medium | 3 | 3 | M02-area-only rejected | Not included |
| live-joker-adjacency-v2 | medium | 3 | 3 | M02-stale-index rejected | Not included |
| isolated-card-wear-v2 | medium | 3 | 3 | M04-additive-refresh rejected | Not included |
| durable-charge-v2 | hard | 3 | 3 | M06-display-only rejected | gold-journal passed |
| shop-price-coherence-v2 | hard | 3 | 3 | M04-stale-accepted rejected | gold-ledger passed |
| pack-choice-commit-v2 | hard | 3 | 3 | M07-repeat-commit rejected | gold-journal passed |

Difficulty remains **uncalibrated**. Engine-validated tasks: 10; public candidate
packages: 10; calibrated tasks: 0. Formal untrusted/disposable-host integration:
not implemented. The approved local maintenance bridge is the only new native
execution claim.

The final matrix spent 21,465.322 seconds (about 5 h 58 min) in its 74 workflows.
Per-process median preparation/startup/test/exit times were 14.25/15.51/43.93/1.90
seconds. Measured per-process directories ranged from 6,656,206 to 15,413,510 bytes,
with 1,811,188,448 bytes summed across processes. Sizes were measured after exit
but before final result/cleanup JSON, and are not total retained platform-state
size. See `metrics-native-v1.json`; the timing totals exclude development, pilot
and smoke work.

## Source, packaging and checks

- Pilot adapter `0f1dcc9290865d8f7539ae19441616cbfef104494fdd61cfc8667af147ab3b63`:
  fresh real smoke plus one growth gold/base pair. Gold passed all 18 checks;
  base completed and failed the declared cases. Both exited normally.
- Final adapter `3f52a81081c7ddb00856caacfe9c71fe7d3e7e15018e047e3ea0c25e1aad2cd3`:
  adds strict rejection of extra private files before import. Its wheel source
  bytes match all 13 package Python files. No private/licensed assets in the wheel.
- Wheel SHA-256: `84cfd11134484c1941024b2cbe0eb9e631df5e47ac698738ef2f5c959593f318`.
- 455 platform/pack source assets frozen in `native-source-freeze-v1.json`.
- 149 related tests passed; 57 Balatro tests also passed against the installed wheel.
- Ruff passed; all 16 owned source/script files passed Mypy. Web lint/test/build
  and Git diff checks passed. Seven declared shell entry points passed Bash syntax.
- Final installed-wheel smoke `20260921-015158-3f1b53f0` passed with normal cleanup.
- Preservation preflight: 501 original PoC frozen files and 76 staged files intact;
  original SWE-Game checkout clean. Fixed dependency/protection audit passed.

## Evidence binding and replay

`NATIVE-VALIDATION-PLAN-v1.md` predeclared 60 gold/base workflows (168 native
processes), then 14 targeted full workflows (40 processes). Each received a new
strict anonymous attempt and exactly one installed CLI scoring invocation. The
pilot and two smoke runs are separate from those final counts.

Private local records: `.test-state/bnf1/controls/` and
`.test-state/bnf1/targeted/`. Both contain `complete.json`, generated after all
declared outcomes matched. The final summary independently rechecked raw response,
CLI, cleanup and source hashes rather than trusting completion labels. The last
maintenance audit confirmed protected data and fixed dependencies unchanged and
verified all ten task import closures. The preservation audit confirmed all 501
original frozen PoC files, all 76 pre-existing staged files and the clean original
SWE-Game checkout. No original source, pins or historical result was rewritten.

Machine-readable delivery:

- `validation-native-v1.json`: final platform outcomes and bound record hashes.
- `runtime-manifest-native-v1.json`: wheel, source, adapter, engine environment,
  original harness, task and candidate identities; Python 3.12/3.13 boundary.
- `metrics-native-v1.json`: actual timing, size and normal-cleanup aggregation.
- `preservation-native-v1.json`: final bound dependency/protected-data audit and
  delivery-time source/index/read-only-repository preservation checks.
- `regression-scope-native-v1.json`: every newly executed role and every retained
  historical role not rerun, plus unexecuted paths.
- `native-source-freeze-v1.json`: 455 frozen platform/pack source assets;
  SHA-256 `56ed6461eb2ecfad5ee2a0ad3ae6dc1a50e25b3a41db1d832ac4c689f1501270`.
- `REPLAY-native-v1.md`: fresh-state preparation, smoke, installed CLI matrix and
  verification commands.

The actual entry was installed `prepare-attempt` / `run-attempt`, not a native
engine invocation through the generated `score-exam.ps1` wrapper. Arbitrary
external candidate hashes remain refused until separately reviewed. The original
108-flow / 309-process PoC batch remains historical and is not counted here.

During waiting, the Codex tool connection timed out and was later resumed. The
existing batch continued to completion; no game action or completed workflow was
reissued. A separate historical-format diagnostic initially supplied an outer
record envelope instead of its nested result; the corrected v2 diagnostic is
retained alongside that failed diagnostic. Neither is fresh engine evidence and
no grader assertion was changed in response.

## Failed and unavailable repository checks

Full Mypy: 45 errors in 10 unchanged POSIX-related files on Windows. Full pytest:
7 collection errors from unavailable `fcntl` in authoring imports; the full suite
did not execute. `devenv` and ShellCheck are unavailable; direct local tools were
used and ShellCheck remains unrun. No packages/system tools were installed to
hide those limitations. These are outstanding whole-repository gates, regardless
of the native matrix outcome; this work is not an all-checks-passing release.

Difficulty remains authored 3 easy / 4 medium / 3 hard, uncalibrated. Formal
Rhenium untrusted integration and arbitrary external submissions remain unimplemented.
No commit, push, PR, fourth difficulty tier or eleventh task is produced.
