# DarkRP benchmark pack

Multi-defect regression tasks built from [DarkRP](https://github.com/FPtje/DarkRP)
(MIT), a Garry's Mod roleplay gamemode written in GLua. Each task boots a real
headless Garry's Mod dedicated server and runs a
[GLuaTest](https://github.com/CFC-Servers/GLuaTest) suite against the agent's tree.

```text
benchmarks/darkrp-core/
├── benchmark.json            schema-v2 plugin and pack selection
├── catalog.json              seven tasks, bilingual metadata
├── runtimes.json             the digest-pinned dedicated-server image
├── exams/                    the public problem statement for each task
└── private/harbor/           the Harbor task packages (environment, tests, solution)
```

The pack is discovered and executed by the Hub through the `rhenium-garrys-mod`
plugin: `rhenium packs` lists `garrys-mod/darkrp`, and evaluation runs through the
plugin's evaluator rather than by invoking Harbor by hand. See
[Garry's Mod support](../../docs/games/garrys-mod.md) for runtime setup.

## Tasks and public metadata

The pack contains seven multi-problem repair tasks. Catalog 1.1.0 retired
`darkrp-job-loadout-regressions` because it was saturated and no longer discriminated;
its exam and Harbor package stay here as history. Public exams and catalog
summaries describe only player- or staff-visible observations. They intentionally
omit defect counts, subsystem maps, diagnoses, internal identifiers, private case
counts, and per-case model misses. The detailed construction history and validation
matrices remain in the private Harbor metadata available to maintainers.

This separation applies to the Hub too: `/api/tasks` reads `catalog.json`, so a
catalog summary must not be richer than the authored public exam.

## Validation status

Maintainers validated each task in both directions: the unmodified broken tree
fails, the reference tree passes, and isolated fixes were checked for unintended
coupling. The final runtime and private-runner collector were then rebuilt and run
through Rhenium on a Linux x86_64 host: for the three tasks in the pack's first
release, all three references scored 100, all three bases completed and failed, the
result-mutation control stayed at reward 0, and the over-permissive door mutant failed
only group R. See [`validation/rhenium-controls.md`](validation/rhenium-controls.md).

Every task added since then carries the same evidence: a per-defect matrix in
[`validation/per-defect-matrix.md`](validation/per-defect-matrix.md), plus a Harbor
run of the unmodified tree scoring 0 and of the reference solution scoring 1.

Exact private case counts and model trajectories are not public task metadata. A unit
test or Dockerfile parse is not a replacement for a current real-server run.

## Runtime and model endpoint policy

The Garry's Mod/GLuaTest source image, Debian amd64 base, and uv amd64 image are
pinned by digest. Debian packages come from a dated snapshot with exact requested
versions. `agent-constraints.txt` pins the Python dependency closure used by
`mini-swe-agent==2.4.6` and `litellm[proxy]==1.98.0` for Python 3.11 on Linux x86_64.
Those Python package artifacts are not hash-locked, so the derived Docker image ID
recorded by Rhenium remains the exact local artifact identity; do not describe a
source rebuild as byte-for-byte reproducible.

Rhenium-native model execution uses the operator's configured model base URL and
does not consult Harbor's `[agent]` block. For direct Harbor 0.20+ validation, the
canonical tasks keep an empty allowlist and the job supplies only the hostname of
the selected endpoint:

```yaml
agents:
  - name: mini-swe-agent
    model_name: provider/model
    extra_allowed_hosts:
      - model-gateway.example
```

Generate that hostname from the configured HTTPS endpoint. Do not add a permanent
list of model vendors to `task.toml`; `github.com` and upstream source hosts must
remain unreachable during the agent phase. The environment and verifier phases are
`no-network`.

## The result channel is adversarial, and is treated that way

The submission owns Lua that runs in the **same Lua state** as the test suite, so
everything in the server log is attacker-influenced. An earlier revision of this
pack took the *last* `| PASS: n` line in that log, which a submission could defeat
simply by printing a second, forged summary after the real one.

Before launch, the verifier patches the digest-pinned GLuaTest copy used by that
ephemeral container. Results are copied into private local state before the public
result hook runs; mutation-capable test-discovery, expectation, skip and environment
extension hooks are disabled; and remaining result/completion hooks receive detached
views. A captured local output sink emits one short, nonce-bound record per case plus
one completion record. Splitting the audit is required because the Source console
truncates lines above 1024 bytes. A post-process collector requires the exact private
case set, one completion record, an unchanged patched harness, GLuaTest's clean-exit
state, no crash log, and a consistent terminal verdict. It then writes `result.json`;
the plugin independently checks that schema and case set instead of trusting
`reward.txt` or PASS/FAIL text.

This is defense in depth, not a cryptographic isolation boundary. Submitted code and
the private suite still share one Lua state, so deliberately obfuscated code could
attack globals or inspect runtime state in ways a source scan cannot prove absent.
Direct GLuaTest/marker references, output-function replacement, and submitted native
modules are rejected, but benchmark integrity ultimately also relies on the strict
exam rule that the model must not tamper with the scorer or private harness.

The inner engine timeout is two minutes. Timeouts, unexpected exit statuses, a changed
harness, missing clean-exit evidence, and post-summary crashes are incomplete runs,
not model failures. Status 1 remains accepted only when the other terminal evidence is
consistent because the pinned entrypoint uses it for completed assertion failures.

## Assertion authoring boundary

Private assertions test observable behavior rather than requiring a particular
function, hook name, or patch shape. Maintainers must read a failed submission's
diff before treating a model miss as evidence: if the reported behavior is fixed by
another legitimate mechanism, the assertion is wrong.

## Licensing

The vendored DarkRP trees retain the upstream MIT license and identify their exact
source commits in `catalog.json` and each task's metadata. GLuaTest is distributed
upstream under GPL-3.0; the runtime catalog pins the reviewed public image by digest.
The image also contains the Garry's Mod dedicated server, whose availability from a
public registry is not a grant to redistribute it under an open-source license.

Rhenium pulls and builds these images locally. Do not publish evaluator images or
include their contents in wheels or benchmark archives without a separate license
review. The pinned GLuaTest image does not embed a source-revision or Garry's Mod
build label, so the digest is the current content identity and source-to-image
provenance remains incomplete.
