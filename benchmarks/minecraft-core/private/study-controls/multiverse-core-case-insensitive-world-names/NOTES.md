# minecraft/core/multiverse-core-case-insensitive-world-names — E0 notes

The original role, control and run sections below describe catalog 0.1.0 and
are historical. Current 0.2.0 acceptance is recorded in the task's
[validation record](../../harbor/multiverse-core-case-insensitive-world-names/validation/controls.md).
Dated 0.2.0 maintenance notes are labeled separately.

Repair task vendored from Multiverse-Core (base `1434ca17`, fix PR #3408).

## Roles

- 169 cases: 2 `target` (server), 164 `preserved` (2 server + 162 upstream MockBukkit
  unit tests), 1 `runtime-sentinel`, 2 `static`.
- The upstream unit tests are the existing-contract baseline; two of them
  (`Get world is case insensitive()`, `Create world failed - world exists and loaded
  (case insensitive)()`) map to the case-insensitivity clause and the rest to the
  "every upstream test keeps passing" clause.

## Controls (real Paper 1.21.11 build 132, 2026-09-22)

| control | kind | what it is | result |
| --- | --- | --- | --- |
| `target-negative-remove-still-leaks` | target-negative | lower-cases the unload lookup and removal but not `worldsMap.remove` | 40, fails only `server:mixed-case world can be removed`; admissible |
| `compat-negative-case-sensitive-lookups` | compat-negative | drops every lower-casing so keys are raw names | 10, fails `server:world lookups ignore case` and the two case-insensitivity unit tests; admissible |
| `alternative-a` | alternative | keeps both `HashMap`s and lower-cases the removal sites | 100; admissible |

Starter: 40 (only the two target cases fail). Reference: 100 three times. Tamper
(edited `build.gradle`, deleted `WorldManagerTest.kt`): verdict unchanged at 100.
