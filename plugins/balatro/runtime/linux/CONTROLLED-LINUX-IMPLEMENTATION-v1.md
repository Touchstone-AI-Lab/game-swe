# Controlled Linux implementation, development revision 1

This revision is **in progress**, not a release or a final ten-task validation.
It preserves the original preparation/probe runtime and introduces
`balatro-linux-17459173-controlled-v1` as a separate managed runtime.

## Evidence already obtained

- Actual managed Steam authentication, fixed acquisition and verification passed
  in the earlier v3 preparation receipts. Credentials remain in the independent
  official-client home; the provider session holds an opaque profile reference.
- A clean native visible smoke passed with the process-local OpenAL null backend.
- The byte-identical save probe v3 passed all six required cases in two normally
  exited native processes: operation/save/exit/fresh initialization/single complete
  load/continued play/checkpoint identity. Its operation is
  `save-capability-v1/20261031-042608-f0e52132`.
- A Session-based smoke and sealed growth controls passed their expected outcomes:
  `controls-v1/20261031-043946-0d9ce63b` (smoke),
  `20261031-044046-c7eaeddd` (gold complete pass), and
  `20261031-044335-ccc712bf` (base complete behavioral rejection).
  These are **pilot source versions**, not proof of subsequently edited code.
- The 434-file Linux-local authored pack snapshot contains only source, contracts,
  metadata and documentation (921,006 bytes in revision 1). All copied bytes were
  checked. It contains no game, login state, save or runtime cache. This removes
  measured Windows-mount metadata latency without dropping any integrity check.

The original recipe, probe artifact and all incomplete startup diagnostics remain
unchanged. Source capsules preserve the implementations used for the successful
save probe and the first growth pair.

## Implementation boundary

The new builder consumes the provider-acquired exact Steam source. It either
copies already verified fixed preparation inputs into its own cache or uses the
original fixed recipe. Existing input drift is an error, never a new pin. Pruning
does not remove the original probe's cache. Preparation and verification do not
count as smoke or task execution.

The Linux evaluator consumes the artifact supplied by core, seals the submission,
requires an exact-byte source review, and calls an owned controller process. The
frozen Session, RPC, scenarios, required cases and result classifier are reused.
Both controller and game arm Linux parent-death termination. A process lock
serializes scoring; existing Linux/Windows game-process guards remain. Forced
termination, missing responses and incomplete cases cannot produce a full pass.
An incomplete invoked operation leaves a halt record for diagnosis.

The environment identity includes the artifact, execution profile, kernel,
distribution, libc, Python executable/version and Windows process-guard executable
where applicable. The harness identity includes current plugin source and the
three unchanged controller sources. Task and candidate identities remain separate.
Smoke is reclassified against those inputs, its full cases and normal cleanup;
the existence of an old file or a `passed` flag is insufficient.

`linux_operator` provides explicit current-host smoke/binding and source-review
operations. Neither it nor scoring authenticates, downloads or rebuilds. Game
execution stays visible with gamespeed=1, FAST=0 and HEADLESS=0. This remains a
controlled honest native runner, **not** a disposable untrusted evaluation host.

## Compatibility decision and remaining verification

Adding required managed task bindings deliberately moves the missing-runtime gate
to core. Core records an error and raises its existing "runtime is not prepared"
exception before calling the plugin. Two older product tests assumed the former
unbound evaluator-level incomplete response. Their updates require the new core
gate, zero score/no pass, preserved pack bytes and independent behavior of the
contract plugin. No private benchmark assertion or core behavior was changed.
The Windows local maintenance runner remains in place; Windows is not a host for
the newly declared Linux runtime.

This worktree still carries plugin 0.2.2 while preserving the preparatory artifact's
version-bound identity. It is not a newly published 0.2.2 release. A future release
must make a 0.3.x version/migration decision and revalidate that final identity;
no release or merge readiness is claimed here.

Still pending at this revision: actual preparation of the controlled runtime,
current-source managed smoke, all ten gold/base controls through the managed
entry, repeated save capability, final applicable tests, protection audit, source
manifest and replay report. Earlier Windows evidence is not relabeled as Linux
evidence. No model calibration, formal untrusted integration, commit, push or PR
has been performed.
