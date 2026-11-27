# Disposable evaluation host provisioning runbook

Rhenium currently defines and enforces the provider-neutral contract but does not ship a real
host provider. This runbook lists the evidence required before a Hyper-V, VMware, QEMU or cloud
adapter may be used for formal scoring.

## 1. Prepare a trusted base

1. Start from a documented clean OS image with all security updates reviewed and pinned.
2. Create a dedicated low-privilege `rhenium-evaluator` account with no interactive personal
   profile.
3. Install the exact Rhenium core, required game plugin, benchmark pack and game runtime.
4. Prepare Steam-provided content before sealing the image. Remove Steam login state, Guard
   data, refresh tokens, cloud state and installer caches.
5. Remove Git/SSH configuration, shell history, browser profiles, model API configuration,
   cloud agents, shared clipboard, host-folder integrations and remote-management credentials.
6. Disable automatic runtime, OS and package updates during evaluation.
7. Configure a read-only runtime/benchmark volume and run-scoped writable state, temporary and
   result volumes.
8. Seal the image or checkpoint and record its immutable provider-specific identity.

Do not use a daily-development VM or a checkpoint whose credential inventory has not been
independently reviewed.

## 2. Configure isolation

- Remove the virtual NIC or attach only a provider-enforced null network. An in-guest firewall
  or game offline flag is not sufficient evidence.
- Disable shared folders, clipboard, drag-and-drop, host drives, guest-agent file exchange and
  device passthrough not required by evaluation.
- Apply explicit vCPU, memory, writable disk, process-count, open-file and wall-clock ceilings.
- Make runtime, pack and submitted input read-only inside the guest.
- Permit writes only below `/rhenium/output`, `/rhenium/state` and `/rhenium/tmp` or the adapter's
  reviewed equivalents mapped to those logical paths.
- Configure a bounded result channel that cannot be used to read arbitrary guest files.

## 3. Provider implementation

Implement a separate Python distribution with a `rhenium.evaluation_hosts` entry point. Map the
provider lifecycle to `doctor`, `verify_base`, `create`, `stage_inputs`, `execute`, `destroy` and
`verify_destroyed`. The provider must return typed proofs and non-secret errors only.

The guest entrypoint must run the selected plugin evaluator, apply plugin sanitation, normalize
the result and emit exactly one bounded envelope bound to the request run ID and nonce. It must
not echo arguments, environment, private paths or raw engine output.

## 4. Controlled validation

Before using the provider for model submissions, record all of the following:

- read-only `doctor` output and provider version;
- immutable base identity verification;
- proof that the virtual NIC is absent/disconnected;
- empty credential-name inventory without reading secret values;
- empty inherited-environment inventory;
- read-only input/runtime/benchmark mounts and writable-path allowlist;
- effective CPU, memory, disk, process-count, open-file and timeout limits;
- successful gold/reference evaluation in the real engine;
- failed known-broken or mutation control;
- malformed result, nonce mismatch, timeout and residual-process rejection;
- successful destruction plus an independent lookup proving that the VM, checkpoint/differencing
  disk, mounts and run inputs no longer exist.

GMod Addons validation must use the selected platform's pinned native App 4020 build and
preserve Windows Job Objects or Linux process-group lifetime control inside the guest.
Neither mechanism replaces the provider's isolation and destruction proofs. GMod DarkRP and
addon-repair validation must use each pack's separately prepared Linux GLuaTest runtime
inside the guest; that evaluator container does not replace those proofs either.
DST validation must use a supported macOS/Linux Dedicated Server
and preserve its process-group and Lua resource limits. Evidence from one game does not prove
the other engine path.

## 5. Run formal scoring

```sh
rhenium evaluation-host doctor <provider-id>
rhenium run <game>/<pack>/<task> <submission> \
  --profile full \
  --security-mode untrusted \
  --host-provider <provider-id> \
  --host-image <immutable-image-or-snapshot-id>
```

Accept the score only when `complete=true`, `passed` reflects the evaluator, and
`security.attested=true`, `security.network=none`, `security.credentialsAbsent=true` and
`security.destroyed=true` are all present. Keep the internal attestation with the run record;
publish only the anonymous security summary.

## 6. Cleanup and failure response

If evaluation or destruction fails, do not reuse the instance. Quarantine the provider/image,
verify the hypervisor inventory manually and rotate any credential that may have been exposed.
Do not force a passing state or rerun locally under `honest` while representing it as the formal
result.
