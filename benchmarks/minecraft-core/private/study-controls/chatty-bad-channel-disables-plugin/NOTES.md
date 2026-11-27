# minecraft/core/chatty-bad-channel-disables-plugin — E0 notes

The original role, control and run sections below describe catalog 0.1.0 and
are historical. Current 0.2.0 acceptance is recorded in the task's
[validation record](../../harbor/chatty-bad-channel-disables-plugin/validation/controls.md).
Dated 0.2.0 maintenance notes are labeled separately.

Repair task vendored from Brikster/Chatty (base `7ca46993`, fix `ae832809`).

## Roles

- 147 cases: 2 `target` (server), 142 `preserved` (4 server + 138 upstream JUnit tests),
  1 `runtime-sentinel`, 2 `static`.

## Controls (real Paper 1.21.11 build 132, 2026-09-22, agent-authored scratch verifier)

| control | kind | what it is | result |
| --- | --- | --- | --- |
| `target-negative-unnamed-warning` | target-negative | per-channel catch without the channel id | fails only `server:skipped channel is reported by name`; admissible |
| `target-negative-whole-loop` | target-negative | one catch around the whole channel loop | fails both target cases, no preserved case; admissible |
| `compat-negative-stay-equals-period` | compat-negative | `stay >= period` off-by-one | fails exactly the two preserved configuration cases; admissible |
| `alternative-a` | alternative | independent per-channel guard | 100; admissible |

Starter: only the two target cases fail (138/138 unit). Reference: 100 three times. Tamper
(edited `spigot/build.gradle`, deleted a test): verdict unchanged.

## 0.2.0 compatibility-control correction, 2026-11-04

The old `stay >= period` control is retained on disk as historical evidence but is
not in the current manifest. The expanded target case also requires the valid
boundary channel between two invalid channels to survive, so this control breaks a
target as well as preserved behavior and cannot isolate compatibility loss.
`run-2cc46dae2b4e4fb5` records its failed admission; that result is not relabeled.

The replacement `compat-negative-player-only-info` starts from the reference and
adds a player-only guard to the root information command. It leaves notification
loading and `/chatty reload` unchanged, but loses the public console information
contract. Full real-server run `run-5f685d892d1147a8` completed with every target
passing and the preserved console-information case failing as intended. No grader
assertion or clause-map role is changed to accommodate the control.
