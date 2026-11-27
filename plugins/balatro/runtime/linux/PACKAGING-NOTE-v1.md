# Read-only wheel compatibility finding

Both affected wheels were built using an already available build environment,
without installing or upgrading dependencies. Their 33 Balatro and nine Steam
source files match the reviewed checkout bytes; required data is present and
game, login, token and state assets are absent. This is a package-content check,
not proof of installed-wheel engine execution.

A read-only native extraction/import attempted to verify the current managed
artifact and smoke binding. It failed before starting any game. Diagnostic
comparison found equal resource SHA-256 values but different executable flags:
the source is mounted through `/mnt/c`, while extracted wheel resources are on
the native Linux filesystem. `linux_runtime.recipe_identity()` includes both
fields from `tree(RECIPE)`; the controlled builder incorporates that identity.

- Editable recipe, matching the retained artifact:
  `cd49f82f56d10f03813a5588ad9b6297a6a4802cc768172b1f407ca2239f0f8d`.
- Extracted-wheel recipe:
  `cf4e50c00e76035d0526a6f7a5a5e2a09f5ae30cbfad5234f2584f9f3adb999a`.
- Private receipt: `.test-state/linux-runtime-v1/wheel-readonly-diagnosis-v1.json`.

The check failed closed. No artifact, pin, permission bit, binding or expected hash
was rewritten to accept it. Current engine evidence is for editable-source
execution only. Wheel installation and engine execution remain unrun.

A future runtime version must define stable handling of self-authored resource
modes and test editable/native/wheel preparation separately. Executable checks
on actual runtime binaries and byte checks on fixed components must remain.
The old builder and artifact are historical inputs, not mutable repair targets.
This finding is separate from the proposed Bot partial-write repair.
