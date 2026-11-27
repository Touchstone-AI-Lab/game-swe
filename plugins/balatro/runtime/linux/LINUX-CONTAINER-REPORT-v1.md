# Controlled Linux container validation v1

All ten frozen catalog 0.2.0 tasks completed full gold/base controls through the
actual core `rhenium run` entry: **20 controls, 56 normally exited real game
processes and 912 required outcomes**. Every gold passed; every base completed
and failed for its intended behavior. These are fresh container-v1 results,
separate from the preserved native Windows and WSL records.

The complete original matrix also passed its independent audit: **68 controls,
197 normally exited real game processes and 3461 required outcomes**. Ten golds
and four independent correct alternatives passed; ten bases and 44 mutants
completed and failed for their declared behavior. Every required assertion ran,
and no final control was incomplete. A separate new-byte source-review admission
probe also passed. This document is not a model-calibration result.

## Execution identity and scope

- Plugin 0.3.0; task catalog 0.2.0. Prompts, starters, private assertions, reference
  implementations, validation matrices, pass criteria and task numbers are unchanged.
- Runtime `balatro/balatro-linux-17459173-container-v1`.
- Prepared artifact `sha256:923b754b4bcadadbf03c85ed0b32dcfd2ff7ccaf66d2af26051f4e8d8ead2f72`.
- Exact dependency image `sha256:b0981b3d42fd0bb6919797f2d045221621d44b5c5b9e8aec823619036cc874fb`.
- Execution source frozen at `6fc0504d710a930d40ae5fe0ced40531920d14f6`; later core pack-readiness metadata changes
  are outside the runtime capsule. Fresh core/plugin wheels reverified the same
  source recipe and artifact without writes or game startup.
- Licensed app 2379780, build 17459173, depot 2379781, manifest 3512319404653808464.
  Actual game SHA-256 is `0d75fe164accf3312734d4b37ac98788dd15f0b8e4f9bb8b7f90c4e59de93f47`.
  Native Linux LÖVE loads the game archive supplied by that Windows Steam depot.
- Controlled native Linux x86_64 NixOS host, local Docker daemon, Ubuntu 24.04
  container, Python 3.12, native LÖVE 11.5, Lovely 0.9.0 and Steamodded 26.829.0.
  This profile rejects WSL/Microsoft kernels. Other hosts and remote daemons have
  not been validated.
- Serial, real rendered 800×600 window on an owned Xvfb display, vsync=0,
  gamespeed=1, FAST=0, HEADLESS=0 and null audio. Mesa llvmpipe software rendering
  uses a 16-CPU ceiling, 8 GiB memory limit and 256-process limit.
- Evaluation uses the immutable image ID, no external network, read-only licensed
  content and protected inputs. It performs no authentication, acquisition,
  installation, update or image build. Preparation is explicit.

This is source-reviewed **honest** execution. It does not establish the generic
untrusted/disposable evaluation-host contract. The original approved Bot
partial-write derivation and frozen native assertion protocol are reused;
25-second RPC and 1800-second native controller deadlines remain unchanged.

## Ten full task pairs

| Task | Required outcomes per control | Game processes per control | Gold | Base |
| --- | ---: | ---: | --- | --- |
| growth-v2 | 18 | 1 | complete pass | intended behavior failure |
| reversible-hand-limit-v1 | 17 | 1 | complete pass | intended behavior failure |
| seeded-effect-stream-v1 | 27 | 4 | complete pass | intended behavior failure |
| bounded-generator-v2 | 75 | 5 | complete pass | intended behavior failure |
| deck-removal-consistency-v2 | 56 | 3 | complete pass | intended behavior failure |
| live-joker-adjacency-v2 | 20 | 2 | complete pass | intended behavior failure |
| isolated-card-wear-v2 | 19 | 1 | complete pass | intended behavior failure |
| durable-charge-v2 | 76 | 5 | complete pass | intended behavior failure |
| shop-price-coherence-v2 | 80 | 3 | complete pass | intended behavior failure |
| pack-choice-commit-v2 | 68 | 3 | complete pass | intended behavior failure |

The read-only audit checks the actual game input fingerprints, nonce, loopback
listener PID/port, rendered window observation, full required-case closure,
normal exit code 0, no forced cleanup and unchanged protected inputs. Container
PID namespaces are combined with game PID and nonce; kernel namespace/PID integer
reuse after a container is destroyed is not treated as game-process reuse.

## New-byte source-review admission

A maintenance-only copy of the growth gold received one reviewed Lua comment;
all other source bytes matched the original control. Its new seal was
`66a5886c452abd91502b24a010ed9875d6cb37b73c531c19c2a362a83e1c3000`.
The first core CLI run returned incomplete `submission_review_required`, with
zero native controller invocations, zero game processes and no runtime halt.
After actual source review and explicit backend review of that matching seal,
the same submission passed all **18 required outcomes in one normally exited
game process**. Physical input, nonce, listener, rendered-window and cleanup
receipts were independently checked. This probe is separate from the 68 original
controls and is not a model attempt.

The [machine-readable evidence](validation-linux-container-v1.json) records both
the original matrix and the admission probe without raw case observations or
operator paths.

## Repository and package checks

Checks for executable source revision `0463c595` passed using the existing Lab
Python 3.12 devenv toolchain. The locked Ruff binary uses its existing Nix loader.

- Full Ruff and Mypy: pass.
- Full pytest: **2490 passed, 16 conditional skips, 2 warnings**.
- Frontend lint, tests and production build: pass.
- Required ShellCheck, Bash syntax and `git diff --check`: pass. The seven
  additional shell scripts in this branch also passed syntax and ShellCheck.
- Fresh core-only wheel environment: no game/provider entry points or engine
  packages; `rhenium games` returns an empty list; **314 passed, 21 optional
  extension skips, 1 warning**.
- The read-only Hub query using the new core code and actual prepared state lists
  all ten tasks with `runtime.available=true`: one current prepared runtime and
  three retained historical entries. Pack readiness now follows current task
  bindings; regression coverage includes independently packaged Balatro and
  Slay the Spire catalogues.
- Three fresh wheels were inspected for exact package boundaries, unique entries,
  required resources and source byte identity. The core wheel contains production
  Web assets. No licensed source, native loader, provider credential, cache or
  raw engine log is packaged. Extracted core/plugin wheels reverify the exact
  prepared runtime recipe; the full game matrix ran from frozen source.

The 16 full-suite skips are three unavailable DST-server tests, seven native
Windows Balatro tests, one macOS sandbox test, four GMod native/explicit-audit
tests and one unavailable Palworld-server test. None replaces container-v1 engine
evidence. Core-only skips concern intentionally absent optional extensions.

Remote CI conclusions and their exact source revision are recorded on
[pull request 40](https://github.com/Touchstone-AI-Lab/SWE-Game/pull/40). The retained
dependency-setup failures occurred before tests: PyPI read and connection
timeouts. CI allows longer dependency read/connect timeouts without
changing pins, TLS verification, assertions or game deadlines. This report's
local checks do not imply that a remote workflow passed.

## Retained failures and remaining limits

The original direct generic-helper ELF-loader failure on NixOS, first image
source-permission failure and four-CPU llvmpipe timing failure remain private
evidence. The final artifact is separate from the four-CPU artifact and its halt.
The NixOS acquisition workaround is the documented local wrapper around the
unchanged released helper, not a new helper release or generic NixOS support.

No Windows/macOS/WSL container-v1 support, untrusted host, cross-host portability,
three repetitions of every control, installed-wheel full game matrix or model
study is claimed. Only four tasks have original independent correct alternatives;
the ten tasks are not all admitted to study E0, and E1 calibration was not run.
The seeded-initialization/one-load save boundary remains; blank-MENU direct load
was not repaired.

Use the [operator guide and replay](../../../../docs/games/balatro-container-v1.md).
Raw game/controller receipts, licensed content, saves and provider state remain
operator-local.
