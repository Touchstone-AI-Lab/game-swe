# minecraft/core/chatty-v2-migration-null-spy-format — E0 notes

The original role, control and run sections below describe catalog 0.1.0 and
are historical. Current 0.2.0 acceptance is recorded in the task's
[validation record](../../harbor/chatty-v2-migration-null-spy-format/validation/controls.md).
Dated 0.2.0 maintenance notes are labeled separately.

Repair task vendored from Brikster/Chatty (base `b9a06458`, fix `f20b64b3`); the server
starts with a seeded legacy `tests/seed/Chatty/config.yml` that has no spy section.

## Roles

- 58 cases: 4 `target` (server), 50 `preserved` (2 server + 48 upstream JUnit tests),
  1 `runtime-sentinel`, 2 `static`.

## Controls (real Paper 1.21.11 build 132, 2026-09-22, agent-authored scratch verifier)

| control | kind | what it is | result |
| --- | --- | --- | --- |
| `target-negative-migrator-only` | target-negative | migrator half only | fails only `server:spy section with only enable reloads`; admissible |
| `target-negative-loader-guard-only` | target-negative | loader half only | fails only the two migrated-format targets; admissible |
| `compat-negative-ignore-explicit-format` | compat-negative | explicit formats ignored | fails only `server:explicit spy formats survive a reload`; admissible |
| `alternative-a` | alternative | independent fix | 100; admissible |

Starter: exactly the four target cases fail (48/48 unit). Reference: 100 three times. Tamper
(GradleException in both build files, `ConstantsTest.java` deleted): verdict unchanged.
