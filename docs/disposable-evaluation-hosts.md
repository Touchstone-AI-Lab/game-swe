# Disposable evaluation hosts

This document defines the game-neutral security boundary for evaluating model-generated or
otherwise untrusted submissions. It is a core contract. Game plugins continue to own their
engine runtime and evaluator; they may not weaken this policy.

## Threat model

Rhenium has two explicit evaluation modes:

| Mode | Intended use | Security claim |
| --- | --- | --- |
| `honest` | Development, references, mutations and submissions trusted by the operator | Process and evaluator controls only; not safe for hostile code |
| `untrusted` | Formal model-generated or external submissions | Requires a credential-free, networkless, disposable host attested through this contract |

Lua sandboxes, POSIX process groups, Windows Job Objects, read-only mounts, containers and
nonce-bound result protocols are useful controls. None is independently a hostile-code
sandbox. A game mod and its private assertion suite may necessarily share an engine process;
the contract therefore does not promise private-suite secrecy against an actively malicious
submission. The disposable host limits the consequence of that compromise.

The trusted computing base consists of core orchestration, the selected host-provider adapter,
the reviewed immutable base image or snapshot, the guest evaluator wrapper and the physical or
cloud hypervisor boundary. A malicious or incorrectly implemented provider can invalidate the
claim and must not be installed as a formal-scoring provider.

## Provider contract

Providers are independent distributions registered through `rhenium.evaluation_hosts` and
must inherit `DisposableEvaluationHost` from
`rhenium.core.evaluation_host`. The lifecycle is deliberately provider-neutral:

1. `doctor()` performs a read-only capability check.
2. `verify_base()` proves the expected immutable image or snapshot identity and effective
   security controls.
3. `create()` creates or restores one clean instance.
4. `stage_inputs()` injects only the immutable submission and the minimum request metadata.
5. `execute()` runs the complete guest evaluator and returns a bounded result envelope.
6. `destroy()` removes the instance and every run-scoped mutable resource.
7. `verify_destroyed()` independently checks that destruction succeeded.

The core owns lifecycle ordering and validates every proof. Provider-specific implementations
belong in separate adapters; core must not contain Hyper-V, QEMU, Docker, WSL, cloud or
game-specific branches.

An entry point has this form:

```toml
[project.entry-points."rhenium.evaluation_hosts"]
example-host = "rhenium_example_host.provider:ExampleDisposableHost"
```

Provider errors and doctor output must contain non-secret summaries only. They must never
return environment values, tokens, guest credentials, private test content or raw engine logs.

## Host identity and attestation

Every request binds:

- a core-generated run ID and nonce;
- the canonical `<game>/<pack>/<task>` key;
- the selected profile;
- one operator-selected immutable image or snapshot identity;
- the resolved submission directory;
- the common security and resource policy.

The verified host identity records provider ID, image identity, instance ID, platform and
creation time. An attestation is accepted only after the instance is destroyed and destruction
is independently verified. `destroyed=true` without `verified=true`, or any residual resource,
fails closed.

## Security policy

Formal `untrusted` evaluation requires all of the following:

- effective network mode is `none`; an offline game flag is insufficient;
- the guest contains no Steam, Git, SSH, model API or other reusable credential;
- no arbitrary host environment variables are inherited;
- runtime, benchmark inputs and submission are read-only;
- writable paths are restricted to the declared `/rhenium/output`, `/rhenium/state` and
  `/rhenium/tmp` allowlist or a strict subset that still contains the result output;
- CPU, memory, writable disk, process-count, open-file and wall-clock limits do not exceed the
  request policy;
- the base image or snapshot identity exactly matches the operator-selected immutable identity;
- process and filesystem residue is empty before accepting the result;
- the result envelope is bounded, valid JSON and bound to the exact run ID and nonce;
- the guest result contains no private protocol, suite, evidence, command, credential or raw
  runtime-log fields, and does not hide run IDs, nonces, image/instance identity or internal
  paths in ordinary string values;
- destruction and independent destruction verification both succeed.

The provider must construct a clean guest environment from an allowlist. It must not inherit a
host home directory, user profile, credential store, agent environment or arbitrary process
environment. Credential inventory reports names only and must be empty; secret values must
never be inspected or returned to core.

Default maximums are 4 vCPU, 8192 MiB memory, 4096 MiB writable disk, 64 processes, 256 open
files, 900 seconds and a 1 MiB result envelope. A provider may allocate less, but it must not
silently exceed the requested ceiling.

## Input, output and result protocol

The submission is the only mutable operator input staged for a run and is mounted read-only.
Core computes a bounded, deterministic manifest digest over regular files and directories,
rejects links/junctions and detects files that change while they are read. The provider must
reproduce the identity after staging; a digest is not a substitute for quiescing the producer
or for a provider's safe no-follow copy implementation.
The reviewed image already contains the exact Rhenium core, game plugin, benchmark pack,
private evaluator and separately prepared game runtime. Image construction is an explicit
trusted maintenance action and never occurs during evaluation.

The guest writes a single UTF-8 JSON envelope to its bounded result channel:

```json
{
  "runId": "run-0123456789abcdef",
  "nonce": "request nonce",
  "result": {
    "score": 100.0,
    "complete": true,
    "passed": true,
    "checks": []
  }
}
```

The guest wrapper must apply plugin result sanitation and the core
`sanitize_disposable_result()` helper before emitting the envelope. Core still rejects oversized
or malformed output, identity mismatches and any remaining private fields. It does not accept a
partial local score when host verification fails.

Internal run records retain a bounded host attestation containing the run/input/image identity,
effective resource limits, input and result-integrity decisions, residual-process/resource
checks and destruction timestamps. Anonymous output removes that attestation and exposes only
the security summary: mode, provider, networklessness, credential absence, attested state and
destruction state.

## Fail-closed behavior

`untrusted` is explicitly selected with `--security-mode untrusted`. It also requires
`--host-provider` and `--host-image`. Missing or invalid host evidence returns score zero,
`complete=false` and `passed=false`. Rhenium never falls back to local `honest` evaluation.

`honest` remains the compatibility default. Its results now state that they are not attested and
did not use a disposable host. Supplying host options without selecting `untrusted` is rejected
to prevent an operator from believing that isolation was active.

Example:

```sh
rhenium run dst/core/dsmmo-release-regressions ./submission \
  --profile full \
  --security-mode untrusted \
  --host-provider <provider-id> \
  --host-image <immutable-image-or-snapshot-id>
```

Provider discovery and read-only readiness checks are available through:

```sh
rhenium evaluation-host list
rhenium evaluation-host doctor <provider-id>
```

Anonymous `score-exam` wrappers accept the same options. Operators may configure the exact
wrapper command externally with `RHENIUM_EVALUATION_SECURITY_MODE=untrusted`,
`RHENIUM_EVALUATION_HOST_PROVIDER` and `RHENIUM_EVALUATION_HOST_IMAGE`; these variables configure
the trusted orchestrator and are not inherited by the guest. The attempt's opaque scoring
command and task isolation remain unchanged.

The management API exposes `GET /api/evaluation-hosts` and
`GET /api/evaluation-hosts/{provider_id}/doctor`. Model-evaluation requests accept the same
`security_mode`, `host_provider` and `host_image` fields.

## Runtime immutability

The image must already contain a verified runtime. Formal evaluation must not log in, invoke
SteamCMD, acquire, install, update or rebuild an engine. The provider attests image identity;
the game plugin still validates its own runtime/build contract inside the guest. Both checks
are required.

## Known limitations

- The contract cannot make same-process private suites secret from hostile game code.
- A dishonest provider can fabricate proofs; provider source, packaging and deployment are part
  of the trusted computing base.
- Rhenium does not currently ship a Hyper-V, QEMU or cloud provider.
- A container alone is not accepted as a disposable hostile-code boundary merely because it
  uses read-only mounts, capabilities or `--network=none`.
- Resource attestation depends on the provider and hypervisor implementation.

## Incident handling

If a run detects network availability, credential names, unexpected environment inheritance,
identity mismatch, malformed output, timeout, residual process or resource, or destruction
failure, operators must:

1. preserve only non-secret bounded orchestration evidence;
2. mark the run incomplete and non-passing;
3. stop using the affected image/provider for formal scoring;
4. rotate any credential that may have entered the guest;
5. rebuild from the reviewed base and obtain a new immutable identity;
6. rerun provider validation before resuming formal evaluation.

Do not attach guest disks, raw logs or memory dumps to public issues until they have been
reviewed for licensed content, private tests and credentials.
