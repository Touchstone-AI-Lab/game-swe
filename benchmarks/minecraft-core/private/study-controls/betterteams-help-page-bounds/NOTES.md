# minecraft/core/betterteams-help-page-bounds — E0 notes

The original role, control and run sections below describe catalog 0.1.0 and
are historical. Current 0.2.0 acceptance is recorded in the task's
[validation record](../../harbor/betterteams-help-page-bounds/validation/controls.md).
Dated 0.2.0 maintenance notes are labeled separately.

Repair task vendored from booksaw/BetterTeams (PR #994, issue #993).

## Roles

- 54 cases: 3 `target` (server), 48 `preserved` (4 server + 44 upstream JUnit tests),
  1 `runtime-sentinel`, 2 `static`.

## Controls (real Paper 1.21.11 build 132, 2026-09-22, agent-authored scratch verifier)

| control | kind | what it is | result |
| --- | --- | --- | --- |
| `target-negative-overflow-unclamped` | target-negative | prefix and lower bound fixed, overflow still returns the max page | fails only `server:pages past the end show the last page`; admissible |
| `compat-negative-prefix-on-single-help` | compat-negative | prefix also prepended to single-command help | fails only `server:help for one command is unchanged`; admissible |
| `alternative-a` | alternative | own clamp plus prefix from config | 100; admissible |

Starter: exactly the three target cases fail (44/44 unit). Reference: 100 three times. Tamper
(broken `BetterTeams/pom.xml`, deleted `ExtUtilTest.java`): verdict unchanged.
