# Don't Starve Together benchmark pack

This directory contains the `dst-core` repair catalog and its evaluator-owned
assets. Every task vendors a real open-source Don't Starve Together mod with one
or more real upstream fixes reverted. The model repairs the mod from
symptom-only reports, and a hidden suite on the pinned dedicated server grades it.

- `benchmark.json` selects the `dst` plugin and `catalog.json`.
- `catalog.json` lists the tasks, their upstream provenance (repository, SPDX
  licence, base commit, reverted fix commits), the mod settings the server uses
  and the exact frozen case list of each hidden suite.
- `exams/<task-id>.md` contains the public, symptom-only exam of each task.
- `server/<task-id>.lua` contains the private dedicated-server suite.
- `runtimes.json` binds every task to the managed `dst-dedicated-24700372`
  container runtime.
- `private/runtime/dst-harbor-runtime/` is the build context of the pinned
  dedicated-server verifier image.
- `private/harbor/<task-id>/` is the task's [Harbor 1.4 package](private/harbor/README.md).
  Its `environment/mod/` (the starter) and `solution/after/` (the upstream
  reference) are prepared by hand. `private/harbor/scripts/materialize.py`
  generates everything else, including `solution/gold.patch`.
- `private/study-controls/<task-id>/` holds each task's E0 controls, clause map
  and notes.
- `validation/README.md` records the two-way validation and control runs.

| Task | Upstream mod | Licence | Target / preserved cases |
| --- | --- | --- | --- |
| `dst-fixed-bundle-regressions` | DST Fixed (gifts and bundles) | Apache-2.0 | 6 / 7 |
| `dst-fixed-module-regressions` | DST Fixed (six optional modules) | Apache-2.0 | 8 / 8 |
| `composting-together-regressions` | Composting Together | MIT | 8 / 3 |
| `dsmmo-release-regressions` | DsMMO | Apache-2.0 | 7 / 7 |
| `glassic-api-regressions` | Glassic API | Apache-2.0 | 8 / 6 |

Every task's upstream licence file travels with both the starter and the
reference tree. Code that was published only on the Steam Workshop, without a
licence from its author, is not used, even when another repository later
imported it under an open-source licence.

The pack is read-only. Generated public manifests and starter workspaces live
under `.rhenium/hub/packs/dst/core/`, outside this directory. References, gold
patches, hidden suites, controls and evaluator internals are never copied into an
attempt or a model workspace; a model run receives the exam and the starter mod
tree only.

Supported versions, platforms, languages, ownership, and runtime limitations
are documented in [DST benchmark support](../../docs/games/dst.md).
