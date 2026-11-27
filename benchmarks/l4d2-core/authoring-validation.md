# Five additional hard tasks: authoring validation

Historical pack 1.1.0 record. The original counts and controls below are retained
unchanged; current review corrections, 1.2.0 counts, and fresh engine evidence
are in [review-revisions.md](review-revisions.md).

Date: 2026-09-19. Branch: `yzr/l4d2-five-hard`.

The pack now contains ten tasks. The five additions are all `hard`, with 229
private real-server cases across 39 defect groups. Existing frozen task contents
and the original five catalogue entries are unchanged. The complete pack has
438 cases across 76 groups.

| New task | Groups | Cases | NOP | Reference / alternative | Review |
| --- | ---: | ---: | ---: | --- | --- |
| LinGe Director and event ownership | 9 | 41 | 11/41 | 41/41; 41/41 | [Independent review](private/harbor/l4d2-linge-director-state-hard/validation/independent-review.md) |
| Competitive score and round ledgers | 7 | 57 | 17/57 | 57/57; 57/57 | [Independent review](private/harbor/l4d2-competitive-score-lifecycle-hard/validation/independent-review.md) |
| VSLib scheduler and persistence | 8 | 47 | 12/47 | 47/47; 47/47 | [Independent review](private/harbor/l4d2-vslib-scheduler-persistence-hard/validation/independent-review.md) |
| Confogl ConVar transactions | 7 | 41 | 0/41 | 41/41; 41/41 | [Independent review](private/harbor/l4d2-confogl-cvar-transactions-hard/validation/independent-review.md) |
| L4D2Lib map and Tank state | 8 | 43 | 0/43 | 43/43; 43/43 | [Review](private/harbor/l4d2-library-map-tank-state-hard/validation/independent-review.md), [context-free review](private/harbor/l4d2-library-map-tank-state-hard/validation/independent-blind-review.md) |

Each task was assigned a newly created reviewer. Revisions address actual
findings about state ownership, finite callback reentry, delayed work, input
scope, and meaningful engine assertions. The additional context-free L4D2Lib
review formed its own judgment without reading another review. Difficulty is an
authoring assessment supported by those reviews, not an empirical solve-rate
claim. No model calibration experiments were run.

All five public smoke commands pass. Private controls use the real pinned L4D2
build `23990100` and SourceMod `1.12.0.7246` in offline disposable Linux
containers. Per-task `validation/control-receipts.json` binds source, tests,
instructions, metadata, reference files and raw logs. The final five matrices
contain 59 control records, including a repeated LinGe gold control.

All 39 representative report-omission controls fail. Supplementary controls
cover finalized score state, finite ConVar writeback and delayed Tank death.
Confogl's additional `minus-bounded-string` mutation survives; its combined
nested-writeback/string-format path remains a documented coverage limitation.
Alternative controls are reference-derived, not wholly independent solutions.
The zero-scored NOPs fail closed; zero does not mean every raw assertion failed.
L4D2Lib's broken NOP also supplies an invalid client to an observer, causing a
fixture diagnostic to fail; its raw and scored outcomes are distinguished in
the review. See each task's `NOTES.md` for all stated coverage limits.

## Repository checks

- `ruff check src tests`: pass.
- `mypy src tests`: pass on Linux, 39 files checked.
- `shellcheck run-benchmark scripts/prepare-exam scripts/score-exam`: pass.
- `git diff --check`: pass for tracked changes.
- L4D2 plugin tests: all 35 pass on Linux.
- Full repository pytest collection: 789 tests. The initial container run had
  11 environment-dependent failures: eight required ShellCheck, two required
  the Docker CLI/daemon, and one expected the repository's parent to be a normal
  directory rather than `/`. Their targeted rechecks are recorded below.

The Windows-native diagnostic also encountered expected POSIX API, symlink
privilege and Unix-permission limitations. Linux checks use a copied workspace
and project-local dependencies. This work does not claim that the full repository
test suite or game server is natively supported on Windows.

All 11 failed cases pass on targeted recheck after supplying their expected
environment. Twenty ShellCheck-related tests pass using the existing ShellCheck
image's binary; the directory-layout case passes from a nested repository path.
Mindustry passes with the installed Docker CLI. The remaining RimWorld case
passes in the copied Linux check image with access to the existing Docker daemon
for its cleanup inspection. The full suite was not rerun after these targeted
checks. No unrelated production code was changed to make them pass.

These are direct maintainer controls, not new Hub full-profile model experiments.
No commit, push, merge, game download or system package installation was performed.
