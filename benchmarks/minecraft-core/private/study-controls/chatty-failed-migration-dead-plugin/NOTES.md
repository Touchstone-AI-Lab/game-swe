# minecraft/core/chatty-failed-migration-dead-plugin — E0 notes

The original role, control and run sections below describe catalog 0.1.0 and
are historical. Current 0.2.0 acceptance is recorded in the task's
[validation record](../../harbor/chatty-failed-migration-dead-plugin/validation/controls.md).
Dated 0.2.0 maintenance notes are labeled separately.

Repair task vendored from Brikster/Chatty (base `b620b36c`, fix `4072f98b`); the server
starts with a seeded legacy `tests/seed/Chatty/config.yml` whose migration fails.

## Roles

- 63 cases: 3 `target` (server), 56 `preserved` (2 server + 54 upstream JUnit tests, which
  include the clean-migration path), 1 `runtime-sentinel`, 2 `static`.

## Controls (real Paper 1.21.11 build 132, 2026-09-22, agent-authored scratch verifier)

| control | kind | what it is | result |
| --- | --- | --- | --- |
| `target-negative-wipe-instead-of-quarantine` | target-negative | wipes instead of quarantining | fails only `server:failed migration is quarantined and reported`; admissible |
| `compat-negative-backup-moved-into-quarantine` | compat-negative | backup folder moved into the quarantine | fails only `server:legacy configuration is moved aside before migrating`; admissible |
| `alternative-a` | alternative | independent recovery | 100; admissible |

Starter: exactly the three target cases fail (54/54 unit). Reference: 100 three times. Tamper
(GradleException in both build files, a test deleted): verdict unchanged.
