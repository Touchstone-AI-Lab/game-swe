# Minecraft construct validation report

## Official-download runtime — 2026-10-31

### Runtime preparation

- The runtime moved from the `local-files` snapshot to the `official-download` provider. Runs used
  the Lab Linux x86_64 host (Docker 29.8.1, containerd image store), from commit `ac5d446f` in an isolated Hub state, not the operator Hub.
- `rhenium runtime prepare minecraft/paper-1.21.11-132-construct` downloaded
  `paper-1.21.11-132.jar` from `fill-data.papermc.io` into this runtime's own cache and verified
  it (54,846,016 bytes, SHA-256 `5ffef465…fba`).
- The operator's own acceptance record, `packs/minecraft/construct/eula.txt` with `eula=true`, was
  written as the explicit operator step before this preparation. It is separate from the core
  pack's record. The base and all five verifier images were built and verified. Artifact identity:
  `sha256:35004733f61d9eef070278c0e8a82642c2e40ba9f2ee12bf65f9fdec5ccd59ac`.

### Control run

| Task | Control | Run | Build | Real Paper cases | Score | Result |
| --- | --- | --- | --- | --- | --- | --- |
| `coinledger-bank-ledger` | unchanged starter (`nop`) | `run-5401db2f509f473f` | passed | complete: 1/30 passed, 29/30 failed | 10/100 | expected fail |
| `coinledger-bank-ledger` | reference (`solution/after`) | `run-e42e1be9e5714ef6` | passed | 30/30 passed | 100/100 | passed |

Both runs used `rhenium run` with the full profile and container networking disabled. No control
was run on the other four tasks under this runtime.

## Current version 1.3.0 acceptance — 2026-11-04

On the Lab Linux x86_64 host, the operator explicitly recorded EULA acceptance
and prepared and verified `minecraft/paper-1.21.11-132-construct` through
`official-download`. All twenty controls below ran the `full` profile on real
Paper 1.21.11 build 132 in network-disabled Docker containers. Every run completed
and observed every frozen case, including the enabled-plugin sentinel. No
mock/emulated server outcome is substituted for these results.

| Task | Control | Run | Score | Live cases passing |
| --- | --- | --- | --- | --- |
| `blocktrail-block-log-rollback` | `alternative` | `run-b948b3dc3fab4d0a` | 100 | 27/27 |
| `blocktrail-block-log-rollback` | `reference` | `run-be9c9602ed294186` | 100 | 27/27 |
| `blocktrail-block-log-rollback` | `starter` | `run-ab99d73a45e248d8` | 10 | 1/27 |
| `blocktrail-block-log-rollback` | `target-negative-rollback-oldest-first` | `run-ec00cfaa86e549be` | 10 | 26/27 |
| `coinledger-bank-ledger` | `alternative` | `run-e37cebfd3baf456a` | 100 | 30/30 |
| `coinledger-bank-ledger` | `reference` | `run-05d2634438674162` | 100 | 30/30 |
| `coinledger-bank-ledger` | `starter` | `run-849e2fff45974cd2` | 10 | 1/30 |
| `coinledger-bank-ledger` | `target-negative-fee-rounded-to-nearest` | `run-c3a70b5db1bd4018` | 10 | 29/30 |
| `recipesmith-config-recipes` | `alternative` | `run-ed1b704696c145b2` | 100 | 18/18 |
| `recipesmith-config-recipes` | `reference` | `run-778a4a1acf364c54` | 100 | 18/18 |
| `recipesmith-config-recipes` | `starter` | `run-1d3d400e23764ba4` | 10 | 1/18 |
| `recipesmith-config-recipes` | `target-negative-enable-waits-for-reload` | `run-3e997ff97b0949b6` | 10 | 17/18 |
| `towncrier-timed-announcements` | `alternative` | `run-e11754eb3f66462c` | 100 | 20/20 |
| `towncrier-timed-announcements` | `reference` | `run-ad0897f9ea2c4cd7` | 100 | 20/20 |
| `towncrier-timed-announcements` | `starter` | `run-8e2262fea4b04b64` | 10 | 1/20 |
| `towncrier-timed-announcements` | `target-negative-interval-keeps-old-timer` | `run-892ee3d749cf48da` | 10 | 19/20 |
| `wardstone-region-protection` | `alternative` | `run-121eb38c1cbc45fc` | 100 | 27/27 |
| `wardstone-region-protection` | `reference` | `run-d3621d6356bf4cad` | 100 | 27/27 |
| `wardstone-region-protection` | `starter` | `run-89fbffe0a5214c1d` | 10 | 1/27 |
| `wardstone-region-protection` | `target-negative-trust-any-region` | `run-7ee83c8ea45b4b0c` | 10 | 25/27 |

The unchanged skeletons fail every target and pass their sentinels. Each negative
fails an intended target. Every reference and alternative passes every case.
Construct tasks have no preserved-contract baseline and are not qualified for the
joint compatibility analysis.

The first current-version CoinLedger, BlockTrail and Wardstone alternatives failed
new public requirements (combined fee-account credit, exact block states and fluid
destinations respectively). Their original failed executions are retained. The
three alternatives were maintained to implement those requirements and rerun in a
separate evidence state. They are extensions of the historical independent
implementations, not new untouched independent attempts. The exam, skeleton,
reference, assertions, case identities and scoring are unchanged. TownCrier and
RecipeSmith's original alternatives passed the current suite without edits.

The first control batch used the current 1.3.0 suite but inherited a stale 1.1.0
version field from its clause maps. All five maps now match catalog 1.3.0, and a
regression check requires matching versions and exact server/unit case sets. The
twenty runs listed above are fresh executions with the corrected metadata; earlier
records retain their original version fields and run IDs. Every selected execution
also matches the prepared task's exact immutable image ID. TownCrier and
RecipeSmith retain the author-approved checkpoint reductions documented below;
full evaluation covers all 122 current required server cases.

Raw control/execution records and runtime identities remain outside the repository
under the operator's isolated validation data. No model experiment is claimed by
this acceptance record. Historical evidence below retains its original status.


## Version 1.3.0 — 2026-09-26

### Runtime preparation

- Paper 1.21.11 build 132, SHA-256 `5ffef465eeeb5f2a3c23a24419d97c51afd7dbb4923ff42df9a3f58bba1ccfba`.
- Runtime `minecraft/paper-1.21.11-132-construct` is registered and ready. Runtime artifact identity: `sha256:b555eadf44912fc8d5bb918c5c9448b391e6cbf2c59c18b539cb826d984c7cb3`.
- Verifier images reused label-checked local artifacts; Recipesmith was assembled offline from the existing CoinLedger Maven cache. The full runtime artifact passed the builder's image and label verification.

### Control run

| Task | Control | Run | Build | Real Paper cases | Score | Result |
| --- | --- | --- | --- | --- | --- | --- |
| `coinledger-bank-ledger` | reference (`solution/after`) | `run-e74cba3d4c304809` | passed | 30/30 passed | 100/100 | passed |
| `coinledger-bank-ledger` | unchanged starter (`nop`) | `run-aa902c0654c74d2e` | passed | complete: 1/30 passed, 29/30 failed | 10/100 | expected fail |
| `blocktrail-block-log-rollback` | reference (`solution/after`) | `run-1c31e7504b1149ec` | passed | 26/27 passed; one expected log line omitted the two documented block-data fields | 10/100 | failed control assertion |
| `blocktrail-block-log-rollback` | reference (`solution/after`) | `run-07e9914899d34257` | failed | not run; starter snapshot was from another task and yielded no BlockTrail jar | 0/100 | incomplete |
| `blocktrail-block-log-rollback` | reference (`solution/after`) | `run-3fd8de1d24a0496f` | passed | not run; grader suite did not compile against the submission | 10/100 | incomplete |
| `blocktrail-block-log-rollback` | reference (`solution/after`) | `run-2b58ec2f6c5b4173` | passed | 27/27 passed | 100/100 | passed |
| `blocktrail-block-log-rollback` | unchanged starter (`nop`) | `run-5521010d022c4d0c` | passed | complete: 1/27 passed, 26/27 failed | 10/100 | expected fail |
| `towncrier-timed-announcements` | reference (`solution/after`) | `run-c4d9feb64ef24e74` | passed | 20/20 current cases passed | 100/100 | passed |
| `wardstone-region-protection` | reference (`solution/after`) | `run-0c66200c6615412a` | passed | 27/27 passed | 100/100 | passed |
| `wardstone-region-protection` | unchanged starter (`nop`) | `run-e289d942c4d84a89` | passed | complete: 1/27 passed, 26/27 failed | 10/100 | expected fail |
| `recipesmith-config-recipes` | reference (`solution/after`), before removal | `run-584c4b4f4e4843a7` | passed | 18/19 passed; all 18 cases retained in v1.3.0 passed, retired permission-case failed in its inventory setup | 10/100 | prior-suite run failed only on retired case |
| `recipesmith-config-recipes` | unchanged starter (`nop`), v1.3.0 | `run-c6ecde38476d4369` | passed | complete: 1/18 passed, 17/18 failed | 10/100 | expected fail |

The CoinLedger reference and NOP runs used Paper 1.21.11 build 132 through `rhenium run` with the full profile and container networking disabled. Paper logged non-fatal DNS errors while fetching public version/key data; it continued startup.

The BlockTrail twelve-field assertion now matches the exam document. The cached verifier image had retained CoinLedger suite files because Docker merged the copied suite directory; deleting the old directory before copying the task suite fixed grader compilation. CoinLedger, BlockTrail, TownCrier and Wardstone each have reference and NOP controls on Paper. TownCrier and RecipeSmith have author-requested checkpoint reductions recorded in their task validation files. RecipeSmith's prior reference run passed every case retained in v1.3.0, but the run itself remained failed on the subsequently removed case. Its current NOP control is a complete expected failure.

No model task experiment was run. Repository-wide lint and test gates were not run; the earlier construct pack static suite result was 35 passed.

## Historical version 1.0.0 records

Per-task historical controls are in `../<task-id>/validation/controls.md`; E0 notes and case maps are in `../../study-controls/<task-id>/`. Those run IDs and results apply to version 1.0.0.
