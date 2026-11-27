# Advanced Palworld controls — catalog 1.1.0

Measured on 2026-09-19. These five new tasks use the existing catalog schema,
15-point integration rubric and full-profile engine requirement. Their package
versions start at 1.0.0; the additive catalog version is 1.1.0. The original five
task entries and their authored assertions/reference implementations are unchanged.
No model attempt or model pass-rate measurement was performed.

## Direct evaluator controls on a real dedicated server

The controls invoked `PalworldEvaluator.evaluate(..., profile="full")` directly,
using the existing throwaway installation at `D:\PalServerBench\PalServer`.
They are actual Windows UE4SS process runs, not Harbor simulation, but do not
claim to exercise the Hub prepare-attempt/run-attempt pipeline. Direct evaluator
calls do not allocate anonymous Hub run IDs.

Runtime content identity (SHA-256, measured on this host):

- `Pal/Binaries/Win64/PalServer-Win64-Shipping.exe`:
  `0498aba32278914f822d9a9d3e218ec0fda577c1a5ab7db481f8590398364d3a`
- `Pal/Binaries/Win64/ue4ss/UE4SS.dll`:
  `fb1839ee91f71f83d508d44a2763a15ac1bb0c5fb4e504ac0fcfca64376a054a`

These identify the local tested binaries, not a newly pinned distribution or a
claim for another installation. The earlier control record's Steam build number
has not been independently re-established for this run.

| Task | Reference full | Real server cases | Nop | Service-only mutant |
| --- | --- | --- | --- | --- |
| outbox-receipt-recovery | 100, complete/pass | 4/4 | 0, incomplete/fail | 90, complete/fail, 3/4 |
| pal-workforce-optimal-matching | 100, complete/pass | 4/4 | 0, incomplete/fail | 90, complete/fail, 3/4 |
| raid-event-watermark | 100, complete/pass | 4/4 | 0, incomplete/fail | 90, complete/fail, 3/4 |
| guild-consistent-checkpoint | 100, complete/pass | 4/4 | 0, incomplete/fail | 90, complete/fail, 3/4 |
| world-epoch-fenced-timers | 100, complete/pass | 4/4 | 0, incomplete/fail | 90, complete/fail, 3/4 |

Nop has no entry point, so its server assertions cannot execute; it correctly
fails required files, syntax, behavior, implementation depth, integration and
headless checks. Each service-only mutant preserves its correct pure core and
all static/integration checks, but replaces one forwarding method with a dummy
success (`Drain`, `Plan`, `Observe`, `Cut`, or `Ack`). Only the headless check
fails, specifically the distinguishing protocol sequence.

The engine assertions verify UE4SS mounting and trusted service calls against
controlled protocol data. They do not claim to change actual game inventory,
work assignments, damage, or proprietary save files. Outbox inventory and journal
effects are explicitly injected adapters. The selected mods registry was restored
and temporary benchmark mod directories removed; no test server was left running.

Initial outbox/workforce reference runs failed to load because top-level return
prevented the evaluator's appended assertion loader from compiling. The new entry
scripts and public contracts were corrected, a tail-injection regression test was
added, and both were rerun successfully. These initial failures are not passes.

## Portable and adversarial controls

- All ten portable reference fixtures pass; all ten empty starters fail in the
  checked-in Lua 5.4/simulated UE4SS verifier.
- Fifteen pure-core mutants (three per new task) are rejected by semantic
  assertions, rather than missing-file or syntax checks.
- Workforce tests compare small generated graphs to independent exhaustive
  matching and exercise a dense 12-by-12 graph. Checkpoint tests independently
  enumerate small cut vectors and exercise 16 shards with 256 events each.
- Watermark tests enumerate event permutations with intermediate reloads.
  Outbox tests cover ambiguous delivery and durable-write failure boundaries.
  Epoch tests interleave stale confirmations, retry generations and world changes.
- Reference lifecycle tests cover delayed world readiness, non-dedicated worlds,
  repeated mounting callbacks, exact hook release, stale callbacks and injected
  evaluator tails.
- Palworld tests excluding the separate Bash launcher module: **95 passed**, with
  the explicit test-server root configured. Python was 3.13.5 in the existing
  workspace environment; this is not a Python 3.12 runtime validation claim.
- All four Bash launcher tests pass with Git Bash placed before the Windows
  WSL launcher on PATH, including anonymous bundle creation for all ten tasks.
  Together these targeted runs total **99 passed**, without skips.

Tests are under `plugins/palworld/tests/test_palworld_advanced_tasks.py` and
`test_palworld_harbor_tasks.py`. Generated traces, mutant copies and complete
local evaluator reports remain in ignored `.test-state/`, never in this pack.

## Repository checks and limits

- Ruff over `src plugins providers tests` and the changed materializer: pass.
- Mypy using `--platform linux`: pass, 90 source files. Native Windows Mypy:
  26 errors in five existing files involving POSIX resource/signal/process APIs;
  no type suppressions or platform implementation changes were introduced.
- Full pytest on the default Windows environment: 184 passed, 20 failed,
  2 skipped at the recorded run. Failures include WSL path translation, POSIX
  shell/process assumptions, symlink privileges, a frozen Isaac checksum mismatch,
  a DST timeout test and Steam helper execution. The frozen Isaac assets and
  expected checksum were not changed. This is not a green whole-repository gate.
- Web lint, test (1 test), and production build: pass after `npm ci`; lint reports
  eight existing warnings. The lockfile is unchanged and `web/dist/.keep` retained.
- Bash syntax: all ten new Harbor entry scripts pass using the available WSL Bash.
- ShellCheck and `devenv` are unavailable on this host and its default WSL distro;
  their prescribed commands were not run. Native tools above are fallback evidence.
- Docker daemon is unavailable, so image builds and actual Harbor oracle/nop jobs
  were not run. Portable verifier passes are not container-build evidence.
- `git diff --check`: pass.

The tasks are authored advanced engineering problems, not empirically calibrated
claims that a named model cannot solve them. Their hardness comes from exact
optimization, uncertainty, causal closure and interacting state transitions.
