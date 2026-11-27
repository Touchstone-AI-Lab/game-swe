# Don't Starve Together Harbor task suite

This directory exports the five `dst-core` repair tasks as independent
[Harbor 1.4 packages](https://www.harborframework.com/docs/tasks). Exams,
server suites, case lists and pass criteria are the catalog's; the export changes
none of them.

Every task has the standard Harbor layout:

```text
task.toml
instruction.md
environment/Dockerfile
environment/mod/...          the starter: the upstream mod with fixes reverted
tests/Dockerfile
tests/test.sh
tests/verify.py
tests/pack/{catalog.json,server/<task>.lua}
solution/after/...           the reference: the upstream mod with its fixes
solution/gold.patch          starter -> reference, generated
solution/solve.sh
```

The evaluated agent receives only the starter in `/app/mod`, in an image that
contains no verifier, suite, reference or server. After the agent phase Harbor
builds `tests/` into a separate, networkless verifier container. Only the
`oracle` control uses `solution/solve.sh`, which replaces `/app/mod` with
`solution/after/`. References, gold patches and private suites are maintenance
assets: they are never copied into an anonymous attempt or a model workspace.

`task.toml` records the upstream repository, SPDX licence, base commit and
reverted fix commits, and `gold_patch_origin = "upstream"`: every gold patch is
the upstream fix, with no injected defects.

## Verification boundary

`tests/Dockerfile` starts from the locally built
`gcb-dst-dedicated-verifier:24700372` image described in
[`../runtime/dst-harbor-runtime`](../runtime/dst-harbor-runtime/README.md). It
contains the real headless dedicated server (Steam app 343050, build 24700372)
and a byte-for-byte copy of the repository's DST evaluator. `verify.py` is a thin
wrapper that runs that evaluator at the `full` profile over `/app`, so the
Harbor reward is exactly the Rhenium verdict: reward 1 only when the
submission-shape check passed and every dedicated-server case of the frozen case
list ran and passed. A missing server, an incomplete run, a missing or extra
case, a crash or a malformed report yields reward 0. `result.json` records
`real_dst_server_ran`.

The container has no network and the Hub path additionally drops all
capabilities, but the private suite and the submission share one Lua state inside
the server. This is repeatability and containment for honest runs, not a
boundary against hostile submissions; formal untrusted scoring still requires the
disposable-host contract.

The Rhenium Hub uses the same images: `rhenium run dst/core/<task> --profile full`
executes the task's verifier image and returns its full report, failing closed
unless the report and the reward agree.

## Versions and regeneration

- Format reference: Harbor schema 1.4 at revision
  `9a2e3b135cc8fb1e41131020f83370cb2f12ae93`.
- The catalog is `dst-core` 4.0.0. Its four hardened packages are at version
  2.0.0; `composting-together-regressions` is still at 1.0.0.

Canonical task content remains in `catalog.json`, `exams/`, `server/` and each
task's hand-prepared `environment/mod/` and `solution/after/`. After an
intentional authoring or evaluator change, regenerate the derived assets from the
repository root:

```sh
python benchmarks/dst/private/harbor/scripts/materialize.py
```

The script never writes the starter or the reference trees.

## Controls

With the base image built, run one task's controls with Harbor:

```sh
harbor run --path benchmarks/dst/private/harbor/dsmmo-release-regressions --agent oracle -y
harbor run --path benchmarks/dst/private/harbor/dsmmo-release-regressions --agent nop -y
```

`scripts/validate-task.sh <task-dir> <results-dir>` and
`scripts/validate-all.sh <results-dir>` mirror the same separate-verifier flow
with plain Docker for hosts without the Harbor CLI: the unchanged starter must
score reward 0 and the reference reward 1. Results must be written outside the
benchmark pack.

Recorded evidence and known limitations are in
[`../../validation/README.md`](../../validation/README.md).
