# DST Harbor validation record

All runs below used Linux x86_64 (NixOS host, Docker 29.8.0), the verifier base
image built from `private/runtime/dst-harbor-runtime`, and the real headless
dedicated server: Steam app 343050, build 24700372. Every verifier container ran
without network. This record is for catalog 2.1.0 (ten tasks); the runs are from
2026-09-22.

## Two-way controls

| Task | Docker `oracle` | Docker `nop` | Hub `full` reference | Hub `full` empty starter |
| --- | --- | --- | --- | --- |
| `camp-supply-ledger` | reward 1.0 | reward 0.0 | complete, passed, 100 | not passed |
| `container-transfer-transaction` | reward 1.0 | reward 0.0 | complete, passed, 100 | not passed |
| `rescue-dispatch-queue` | reward 1.0 | reward 0.0 | complete, passed, 100 | not passed |
| `world-rule-ballot` | reward 1.0 | reward 0.0 | complete, passed, 100 | not passed |
| `combat-target-arbiter` | reward 1.0 | reward 0.0 | complete, passed, 100 | not passed |
| `waystone-route-network` | reward 1.0 | reward 0.0 | complete, passed, 100 | not passed |
| `status-effect-stack` | reward 1.0 | reward 0.0 | complete, passed, 100 | not passed |
| `fuel-ration-allocator` | reward 1.0 | reward 0.0 | complete, passed, 100 | not passed |
| `trade-escrow-exchange` | reward 1.0 | reward 0.0 | complete, passed, 100 | not passed |
| `loot-roll-arbiter` | reward 1.0 | reward 0.0 | complete, passed, 100 | not passed |

- Docker columns: `scripts/validate-all.sh`, which builds each task's verifier image
  from its `tests/` directory and runs the empty starter and `solution/solve.sh`
  against it; every oracle run recorded `real_dst_server_ran: true`.
- Hub columns: `rhenium auth login container`, `rhenium runtime prepare
  dst/dst-dedicated-24700372` (ten task images), then `rhenium run dst/core/<task>
  <submission> --profile full` through the managed container runtime in an isolated
  state directory.
- For each reference the full report was 100/100: required files, Lua syntax, all
  six hidden behavior cases, implementation depth, every integration contract and
  every dedicated-server assertion.
- The Harbor CLI (`harbor run --agent oracle|nop`) was run for the five original
  tasks at catalog 2.0.1 only; it has not been rerun for catalog 2.1.0.

An empty starter never loads as a mod, so the server reports no case list and the
result is incomplete as well as failed. That is the evaluator's existing
behavior and is why the Hub column says "not passed" rather than "complete".

## Alternative and negative controls

Each task also has a structurally different implementation written from the public
exam and a set of single-obligation mutants of the reference, under
`private/study-controls/<task>/` (`manifest.tsv`, `clause-map.json`, `NOTES.md`).
Every alternative scored 100 (complete, passed) and every negative ran to completion
and failed on the real server; the failed cases are listed in each manifest.

| Task | Alternatives | Negatives |
| --- | ---: | ---: |
| `camp-supply-ledger` | 2 | 1 |
| `container-transfer-transaction` | 1 | 3 |
| `rescue-dispatch-queue` | 2 | 1 |
| `world-rule-ballot` | 1 | 4 |
| `combat-target-arbiter` | 2 | 1 |
| `waystone-route-network` | 1 | 13 |
| `status-effect-stack` | 1 | 13 |
| `fuel-ration-allocator` | 1 | 20 |
| `trade-escrow-exchange` | 1 | 14 |
| `loot-roll-arbiter` | 1 | 22 |

For the five tasks added in catalog 2.1.0 these controls were produced by authoring
agents and then re-run independently by the maintainer, with identical verdicts.
The negatives of each new task together fail every hidden case and at least three of
its four server cases.

## Catalog 2.1.0 repairs to the original tasks

An audit of catalog 2.0.1 found assertions that a valid implementation of the public
exam could fail. They were fixed at the source rather than worked around:

- `camp-supply-ledger` and `rescue-dispatch-queue`: the server suites called
  `component.OnSave()` without a receiver; they now use a method call, and an
  implementation with ordinary class methods passes (`alternative-b`).
- `combat-target-arbiter`: the tie case was only satisfiable when a source's whole
  threat table decayed from that source's last event. The exam now states per-entry
  linear decay with its formula, the case adds 9 instead of 10 so the tie is genuine,
  and the reference implements per-entry decay.
- `world-rule-ballot`: two assertions that accepted wrong behavior were tightened.
- Every exam publishes the option names, result fields, status strings, thresholds
  and adapter row shapes its suites read, and states the implementation-depth minimum.

## Not run

- macOS, Windows and WSL2 hosts. `runtimes.json` allows them so an operator can
  try Docker there, but only Linux x86_64 has evidence.
- Model-under-test trials on catalog 2.1.0. Only references, alternatives, negatives
  and empty starters were run.
- Disposable-host (`--security-mode untrusted`) scoring.
- Independent human review of the new tasks and of the English exam translations.

## Revalidation after the move to `dst/construct` (2026-09-24)

On 2026-09-24 (UTC+8) the ten tasks were restored from the commit before
`a9b95974` into this pack and revalidated, because the plugin had changed since
they were last validated. The plugin now also serves the repair pack; construct
tasks are graded by the restored construct evaluator
(`rhenium_dst/construct_evaluator.py`), reached through the plugin's dispatch on
the catalog model.

Setup: Linux 7.2.5 x86_64, Docker 29.8.0, shared with other workloads (load
average 12 to 18). `rhenium runtime prepare dst/dst-dedicated-24700372-construct`
built the ten task images on a base image whose SteamCMD and server layers
(Steam app 343050, build 24700372) came from the Docker build cache; only the
layers from `COPY evaluator` on were rebuilt. Prepared artifact identity:
`sha256:2a6a975ab566209bc460454405e9abe38e8d76ec05a9381d5b910c9fd96e3b8d`. Every
run is `rhenium run dst/construct/<task> <submission> --profile full` in the
default `honest` security mode. The reference submission is a copy of
`private/harbor/<task>/solution/reference/`; the empty starter is a copy of
`private/harbor/<task>/environment/mod/` (its `README.md` only).

| Task | Reference | Empty starter |
| --- | --- | --- |
| `camp-supply-ledger` | `run-84000fe0f62b4a6d`: 100, complete, passed | `run-79b2a9a710e345b6`: 0, incomplete, failed |
| `container-transfer-transaction` | `run-709e4356465e4b2b`: 100, complete, passed | `run-ca7926dbcd1749f7`: 0, incomplete, failed |
| `rescue-dispatch-queue` | `run-e663d56a57ef4f40`: 100, complete, passed | `run-1d21bcd873664c21`: 0, incomplete, failed |
| `world-rule-ballot` | `run-b23aa6f12012451b`: 100, complete, passed | `run-9d41a6dcaf7046a0`: 0, incomplete, failed |
| `combat-target-arbiter` | `run-22f7ea6e76594d5f`: 100, complete, passed | `run-01c0103f55a3482b`: 0, incomplete, failed |
| `waystone-route-network` | `run-9cede7c06ebf42ed`: 100, complete, passed | `run-5bc6096a73b64d21`: 0, incomplete, failed |
| `status-effect-stack` | `run-9d7a52342b5649f0`: 100, complete, passed | `run-0bd48c205eb24d0d`: 0, incomplete, failed |
| `fuel-ration-allocator` | `run-436b31d437564809`: 100, complete, passed | `run-0e3c2e1a32714972`: 0, incomplete, failed |
| `trade-escrow-exchange` | `run-1b11c2d926184591`: 100, complete, passed | `run-eede605f92c04115`: 0, incomplete, failed |
| `loot-roll-arbiter` | `run-cab5b4b1775a493d`: 100, complete, passed | `run-205042b743344b14`: 0, incomplete, failed |

- Every reference passed every check: required files, Lua syntax, every
  plain-Lua case, implementation depth, every integration contract and every
  dedicated-server case (three or four per task).
- Every empty starter failed every check and scored 0. It is incomplete by the
  evaluator's design, as before the move: without `modmain.lua` the server suite
  cannot be injected, so the server reports no case list.
- Three invocations ended before evaluation with `database is locked` while other
  Hub processes on the host wrote the shared state database. They produced no
  result and were rerun: the `rescue-dispatch-queue` and `loot-roll-arbiter` empty
  starters and the `loot-roll-arbiter` reference. No complete result was discarded
  or rerun.
- Not rerun after the move: the Docker `validate-all.sh` controls, the Harbor CLI
  trials, and the alternative and negative controls under
  `private/study-controls/`. Their verdicts above are from the evaluator before the
  move. The code that grades construct tasks is unchanged apart from its module
  and class names and the runtime key; the host-side Docker bookkeeping around the
  verifier container now waits up to 300 s (was 10 to 60 s) and the container up
  to 1200 s (was 900 s).
