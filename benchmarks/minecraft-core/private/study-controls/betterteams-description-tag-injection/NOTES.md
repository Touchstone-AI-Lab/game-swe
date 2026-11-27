# minecraft/core/betterteams-description-tag-injection — E0 notes

The original role, control and run sections below describe catalog 0.1.0 and
are historical. Current 0.2.0 acceptance is recorded in the task's
[validation record](../../harbor/betterteams-description-tag-injection/validation/controls.md).
Dated 0.2.0 maintenance notes are labeled separately.

Repair task vendored from booksaw/BetterTeams (PR #986, base `b35644ce`, fix `382d34a6`).

## Roles

- 52 cases: 2 `target` (server), 47 `preserved` (3 server + 44 upstream JUnit tests),
  1 `runtime-sentinel`, 2 `static`. Click/hover events are not observable from a
  player-free sender; the target cases key on the literal tag text.

## Controls (real Paper 1.21.11 build 132, 2026-09-22, agent-authored scratch verifier)

| control | kind | what it is | result |
| --- | --- | --- | --- |
| `target-negative-click-only` | target-negative | escapes only click tags | fails only the hover target; admissible |
| `compat-negative-escape-everything` | compat-negative | escapes every tag | fails only `server:a colour tag in a description still colours the text`; admissible |
| `alternative-a` | alternative | legacy formatter plus prefix | 100; admissible |

Starter: exactly the two target cases fail (44/44 unit). Reference: 100 three times. Tamper
(broken `BetterTeams/pom.xml`, tests deleted/altered): verdict unchanged.
