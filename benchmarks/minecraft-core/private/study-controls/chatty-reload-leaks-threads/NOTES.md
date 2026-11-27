# minecraft/core/chatty-reload-leaks-threads — E0 notes

The original role, control and run sections below describe catalog 0.1.0 and
are historical. Current 0.2.0 acceptance is recorded in the task's
[validation record](../../harbor/chatty-reload-leaks-threads/validation/controls.md).
Dated 0.2.0 maintenance notes are labeled separately.

Repair task vendored from Brikster/Chatty (base `f98b8191`, fix `c7ba4171`).

## Roles

- 91 cases: 3 `target` (server), 85 `preserved` (3 server + 82 upstream JUnit tests),
  1 `runtime-sentinel`, 2 `static`. The Redisson clause is unasserted (no Redis offline).

## Controls (real Paper 1.21.11 build 132, 2026-09-22, agent-authored scratch verifier)

| control | kind | what it is | result |
| --- | --- | --- | --- |
| `target-negative-ticker-only` | target-negative | ticker fixed, bStats leaked | fails only `server:reloads do not leak ticker or bStats threads`; admissible |
| `target-negative-executor-not-shut-down` | target-negative | bStats fixed, executor kept | fails only its two mapped targets; admissible |
| `target-negative-no-null-guard` | target-negative | no guard for an unstarted ticker | fails only `server:cancelling a ticker that never started does not throw`; admissible |
| `compat-negative-metrics-kept-forever` | compat-negative | first Metrics kept | fails only `server:bStats metrics stay scheduled after a reload`; admissible |
| `alternative-a` | alternative | lazy named executor, Metrics owned by Chatty | 100; admissible |

Starter: exactly the three target cases fail (82/82 unit). Reference: 100 three times. Tamper
(GradleException in `build.gradle`, test deleted): verdict unchanged.
