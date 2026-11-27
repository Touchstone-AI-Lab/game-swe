# Garry's Mod Addons Harbor task suite

This directory exports the five `rhenium-gmod-v2` 2.2.0 Addon generation tasks as
independent [Harbor 1.4 packages](https://www.harborframework.com/docs/tasks).
Public exams, hidden and integration suites, Dedicated Server suites, traceability
maps, weights and pass criteria are the catalog's; the export changes none of them.

Every task has the standard Harbor layout:

```text
task.toml
instruction.md
environment/Dockerfile
environment/addon/TASK.md
tests/Dockerfile
tests/test.sh
tests/verify.py
tests/pack/{catalog.json,exams/,sources/,private/tasks/<task>/}
solution/reference/...
solution/solve.sh
```

The evaluated agent receives only the empty `environment/addon/` starter in an
image that contains no verifier, suite or server. The starter file is named
`TASK.md` because the Addons submission validator rejects any file other than
`addon.json`, `lua/**/*.lua` and the known public support files. After the agent
phase Harbor builds `tests/` into a separate, networkless verifier container. Only
the `oracle` control uses `solution/solve.sh`, which copies `solution/reference/`
into `/app/addon`. References and private suites are maintenance assets: they are
never copied into an anonymous attempt or a model workspace.

`solution/reference/` is a generated copy of the task's first canonical reference
under `private/tasks/<task>/references/`. The one-task verifier pack contains the
whole private task tree, references included, because the unmodified catalog
loader validates the mutation matrix against them.

## Verification boundary

`tests/Dockerfile` starts from the locally built
`gcb-gmod-addons-verifier:23150012` image described in
[`../runtime/gmod-harbor-runtime`](../runtime/gmod-harbor-runtime/README.md). It
contains an operator-retained native Linux Dedicated Server (Steam app 4020, build
23150012) and a byte-for-byte copy of the repository's Addons evaluator.
`verify.py` is a thin wrapper that runs that evaluator at the `full` profile, so
the Harbor reward is exactly the Rhenium verdict: reward 1 only when the Addon
tree, syntax, plain-Lua behavior, adapter contracts, every Dedicated Server group
and every declared phase ran and passed with the evaluator's nonce, evidence and
cleanup checks intact. A missing or mismatched server, an incomplete run, a crash
or a malformed report yields reward 0. `result.json` records
`real_gmod_server_ran` and the observed `server_build`.

The container has no network, but the private suite and the submission share one
GMod Lua state, process groups are not a sandbox, and a container is not a
disposable host. This is repeatability and containment for honest runs; formal
untrusted scoring still requires the disposable-host contract.

Unlike DST, this image is not a Rhenium managed runtime: the pinned build can no
longer be downloaded anonymously, so nothing can prepare it from a public source.
The Hub keeps evaluating `garrys-mod/addons` with the plugin-owned native runner.

## Versions and regeneration

- Format reference: Harbor schema 1.4 at revision
  `9a2e3b135cc8fb1e41131020f83370cb2f12ae93`; controls were run with Harbor CLI
  0.23.0.
- Each Harbor package starts at version 1.0.0 and records the catalog task
  version in `metadata.content_reference_task_version`.

After an intentional authoring or evaluator change, regenerate the duplicated
assets from the repository root and rebuild the base image:

```sh
python benchmarks/gmod/private/harbor/scripts/materialize.py
benchmarks/gmod/private/runtime/gmod-harbor-runtime/build-image.sh /srv/rhenium/gmod-server
```

## Controls

```sh
harbor run --path benchmarks/gmod/private/harbor/prop-ownership-quota-registry --agent oracle -y
harbor run --path benchmarks/gmod/private/harbor/prop-ownership-quota-registry --agent nop -y
```

`scripts/validate-task.sh <task-dir> <results-dir>` and
`scripts/validate-all.sh <results-dir>` mirror the same separate-verifier flow
with plain Docker for hosts without the Harbor CLI. Results must be written
outside the benchmark pack.

Recorded evidence and known limitations are in
[`validation/README.md`](validation/README.md).
