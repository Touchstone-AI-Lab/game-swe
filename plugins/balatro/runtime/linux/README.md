# Controlled Linux runtime work

The 0.3.0 [container profile](../../../../docs/games/balatro-container-v1.md)
adds a separately prepared native Linux Lab execution environment. All ten full
gold/base pairs passed their intended outcomes: 20 controls, 56 normally exited
real game processes and 912 required outcomes. The native 0.2.2 records below retain their original
host, version, fingerprints and remaining limitations.

Current container evidence: [full report](LINUX-CONTAINER-REPORT-v1.md) and
[sanitized validation](validation-linux-container-v1.json). All 68 original
controls completed their intended outcomes, using 197 normally exited real game
processes and 3461 required outcomes.

## Historical native 0.2.2 record

Historical evidence is [validation v2](LINUX-RUNTIME-REPORT-v2.md): all ten frozen
tasks completed full gold/base controls through the actual core CLI, totaling
20 controls, 56 normally exited native game processes and 912 required outcomes.
Three independent six-case initialized-load probes also passed. Each candidate
has one complete Linux suite in this batch; older repetitions remain separate.

The runtime uses a new, operator-approved Bot transport derivation and an owned
visible 800×600 process profile. Original dependencies, game, old artifacts,
both earlier halts, protected directories and frozen task semantics are retained.
Execution stays serial, gamespeed=1, FAST=0 and HEADLESS=0, with process-local
null audio. Python 3.12 controls the native Linux engine; the original Windows
PoC's Python 3.13 environment is unchanged.

## Historical native records

- [Full report and remaining limitations](LINUX-RUNTIME-REPORT-v2.md)
- [Machine-readable validation](validation-linux-runtime-v2.json)
- [Final source/runtime manifest](runtime-manifest-linux-v2.json)
- [Version-specific replay](REPLAY-linux-v2.md)
- [Approved transport implementation and source provenance](TRANSPORT-IMPLEMENTATION-v2.md)
- [Rendering diagnosis and retained failures](RENDER-DIAGNOSIS-v1.md)
- [Provider acquisition and cache-reuse boundary](../../../../providers/steam/CONTROLLED-CONSOLE.md)

The later [repository checks v3](REPOSITORY-CHECKS-REPORT-v3.md) pass full Ruff,
Mypy and pytest, frontend and shell checks, with explicit conditional skips and
the approved six-copy integrity gate. Nix/devenv, the stock shell scorer's full
engine path and remote CI remain unrun. These local checks support submission
review, not automatic merge/release approval. No formal untrusted host, cross-host
bootstrap or model calibration is claimed. Runtime preparation remains an explicit
operator action; evaluation never authenticates, downloads, installs, updates or
rebuilds. The v2 engine batch was not rerun or relabeled by this maintenance work.

## Preserved history

The [v1 partial report](LINUX-RUNTIME-REPORT-v1.md),
[v1 replay](REPLAY-linux-v1.md),
[original component-change proposal](COMPONENT-CHANGE-REQUEST-v1.md),
[initial implementation](CONTROLLED-LINUX-IMPLEMENTATION-v1.md) and
[initial engine/audio diagnosis](ENGINE-DIAGNOSIS-v1.md) describe their own revisions.
Their hashes and failure statuses are not rewritten. Approval of the original
proposal is recorded separately in the v2 implementation record.

- [CEF permission boundary](CEF-CONTROL-CHANGE-REQUEST-v1.md)
- [Fixed-depot probe and reconciliation](ACQUISITION-PROBE-RESULT-v8.md)
- [Interactive login and normal exit](AUTHENTICATION-PROBE-RESULT-v6.md)
- [Earlier startup diagnosis](AUTHENTICATION-PROBE-RESULT-v3.md)
- [Earlier provider blocker](AUTHENTICATION-BLOCKER-v2.md)

Private logs, game/client state, checkpoints and receipts remain under operator
state and ignored `.test-state` locations. They are not distributable assets.
Blank-MENU direct load, new tasks, model experiments, system changes, dependency
upgrades, commits, pushes and PR creation are outside this runtime work.
