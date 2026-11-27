# Mindustry construct pack

This directory contains the `rhenium-mindustry-v1` catalog, restored from the commit
before `9b038435` next to the repair pack in `../mindustry-core`. The Hub key is
`mindustry/construct` (`pack_id: construct`).

Ten generation tasks for Mindustry. Catalog 1.1.0 retired `command-rate-limiter`, which
was saturated and no longer discriminated; its files stay here as history. Catalog 1.2.0
adds `blueprint-layout-reconciler`, authored on 2026-11-12 with four single-defect ablations; catalog 1.2.1 renames its plugin so that
no public file contains the task id. Agents implement a server plugin from the public exam
specification, starting from a scaffold that holds only `plugin.hjson`,
`build-reference.sh` and an empty `src/`. Private Harbor tasks contain the oracle
implementation, verifier, and negative-control mutants. Validation results must come
from real executions.

- `catalog.json` is the machine-readable catalog; `exams/<task-id>.md` holds the public
  exams.
- `runtimes.json` binds every task to the `mindustry` runtime (`mindustry/mindustry`),
  which is separate from the repair pack's `mindustry/mindustry-159.7`. The server jar is
  not stored in this repository: the `official-download` provider downloads it from the
  v159.7 GitHub release (URL, size and SHA-256 pinned), and the runtime builder verifies
  the pinned SHA-256 again.
- `private/runtime/Dockerfile` builds the base image `mindustry:159.7`; every task's
  `private/harbor/<task-id>/environment/Dockerfile` builds its evaluator image on top of it.
- `private/harbor/<task-id>/` is the task's Harbor package: `tests/` (hidden verifier and
  grader plugin), `solution/` (oracle) and `validation/` (oracle copy and one
  single-defect ablation). `private/harbor/NOTES.md` records the validation policy and
  the Hub validation runs.

The pack is read-only. Starter workspaces, runtime caches and evaluator images live under
`.rhenium/`, outside this directory. Supported versions, evaluation layers and
limitations are documented in [Mindustry benchmark support](../../docs/games/mindustry.md).
