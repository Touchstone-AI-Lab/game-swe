# minecraft/core/multiverse-core-world-exists-by-key — E0 notes

The original role, control and run sections below describe catalog 0.1.0 and
are historical. Current 0.2.0 acceptance is recorded in the task's
[validation record](../../harbor/multiverse-core-world-exists-by-key/validation/controls.md).
Dated 0.2.0 maintenance notes are labeled separately.

Repair task vendored from Multiverse-Core (PR #3470, base `54900f55`, merge `5f43d756`).

## Roles

- 186 cases: 4 `target` (server), 179 `preserved` (2 server + 177 upstream MockBukkit tests),
  1 `runtime-sentinel`, 2 `static`.

## Controls (real Paper 1.21.11 build 132, 2026-09-22, agent-authored scratch verifier)

| control | kind | what it is | result |
| --- | --- | --- | --- |
| `target-negative-no-import-key-lookup` | target-negative | alternative minus the import lookup | fails only `server:import adopts a loaded Bukkit world addressed by key`; admissible |
| `compat-negative-key-only` | compat-negative | key-only checks | fails only `server:creating or cloning under an existing name is rejected`; admissible |
| `alternative-a` | alternative | WorldManager-only helpers | 100; admissible |

Starter: exactly the four target cases fail (177/177 unit). Reference: 100 three times. Tamper
(GradleException in `build.gradle`, `WorldManagerTest.kt` deleted): verdict unchanged.
