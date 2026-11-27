# minecraft/core/prometheus-exporter-players-total-main-thread — E0 notes

The original role, control and run sections below describe catalog 0.1.0 and
are historical. Current 0.2.0 acceptance is recorded in the task's
[validation record](../../harbor/prometheus-exporter-players-total-main-thread/validation/controls.md).
Dated 0.2.0 maintenance notes are labeled separately.

Repair task vendored from sladkoff/minecraft-prometheus-exporter (base `e8647672`, fix `e7de226`).

## Roles

- 34 cases: 2 `target` (server), 29 `preserved` (2 server + 27 upstream JUnit tests),
  1 `runtime-sentinel`, 2 `static`. The target cases run synchronously on the main thread,
  so a collector that still dispatches to the main thread structurally cannot complete them.

## Controls (real Paper 1.21.11 build 132, 2026-09-22, agent-authored scratch verifier)

| control | kind | what it is | result |
| --- | --- | --- | --- |
| `target-negative-sync-playerdata-count` | target-negative | cheap synchronous count on the main thread | fails only the two target cases; admissible |
| `compat-negative-online-only` | compat-negative | asynchronous but online-only count | fails only `server:players_total reports every known player`; admissible |
| `alternative-a` | alternative | `collect()` override, no scheduler | 100; admissible |

Starter: exactly the two target cases fail (27/27 unit). Reference: 100 three times. Tamper
(broken `pom.xml`, deleted and edited tests): verdict unchanged.
