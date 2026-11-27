# Don't Starve Together Harbor task suite

This directory exports the ten `rhenium-dst-v2` generation tasks as independent
[Harbor 1.4 packages](https://www.harborframework.com/docs/tasks). Prompts,
hidden suites, server suites, weights and pass criteria are the catalog's; the
export changes none of them.

Every task has the standard Harbor layout:

```text
task.toml
instruction.md
environment/Dockerfile
environment/mod/README.md
tests/Dockerfile
tests/test.sh
tests/verify.py
tests/pack/{fixed-v1.json,hidden/<task>.lua,server/<task>.lua}
solution/reference/...
solution/solve.sh
```

The evaluated agent receives only the empty `environment/mod/` starter in an
image that contains no verifier, suite or server. After the agent phase Harbor
builds `tests/` into a separate, networkless verifier container. Only the
`oracle` control uses `solution/solve.sh`, which copies `solution/reference/`
into `/app/mod`. References and private suites are maintenance assets: they are
never copied into an anonymous attempt or a model workspace.

## Verification boundary

`tests/Dockerfile` starts from the locally built
`gcb-dst-dedicated-verifier:24700372` image described in
[`../runtime/dst-harbor-runtime`](../runtime/dst-harbor-runtime/README.md). It
contains the real headless dedicated server (Steam app 343050, build 24700372)
and a byte-for-byte copy of the repository's DST evaluator. `verify.py` is a thin
wrapper that runs that evaluator at the `full` profile, so the Harbor reward is
exactly the Rhenium verdict: reward 1 only when static checks, the sandboxed
plain-Lua suite, the integration contracts and every dedicated-server assertion
ran and passed. A missing server, an incomplete run, a crash or a malformed
report yields reward 0. `result.json` records `real_dst_server_ran`.

The container has no network and the Hub path additionally drops all
capabilities, but the private suite and the submission share one Lua state inside
the server. This is repeatability and containment for honest runs, not a
boundary against hostile submissions; formal untrusted scoring still requires the
disposable-host contract.

The Rhenium Hub uses the same images: `rhenium run dst/construct/<task> --profile full`
executes the task's verifier image and returns its full report, failing closed
unless the report and the reward agree.

## Versions and regeneration

- Format reference: Harbor schema 1.4 at revision
  `9a2e3b135cc8fb1e41131020f83370cb2f12ae93`; controls were run with Harbor CLI
  0.23.0.
- Each Harbor package starts at version 1.0.0. The catalog stays
  `rhenium-dst-v2` 2.0.1.

Canonical task content remains in `exams/`, `hidden/`, `server/` and
`fixed-v1.json`. After an intentional authoring or evaluator change, regenerate
the duplicated assets from the repository root:

```sh
python benchmarks/dst-construct/private/harbor/scripts/materialize.py
```

The script never writes `solution/reference/`; those mods are authored by hand.

## Controls

With the base image built, run one task's controls with Harbor:

```sh
harbor run --path benchmarks/dst-construct/private/harbor/world-rule-ballot --agent oracle -y
harbor run --path benchmarks/dst-construct/private/harbor/world-rule-ballot --agent nop -y
```

`scripts/validate-task.sh <task-dir> <results-dir>` and
`scripts/validate-all.sh <results-dir>` mirror the same separate-verifier flow
with plain Docker for hosts without the Harbor CLI. Results must be written
outside the benchmark pack.

Recorded evidence and known limitations are in
[`validation/README.md`](validation/README.md).
