# minecraft/core/chatty-reload-ignores-chat-commands — E0 notes

The original role, control and run sections below describe catalog 0.1.0 and
are historical. Current 0.2.0 acceptance is recorded in the task's
[validation record](../../harbor/chatty-reload-ignores-chat-commands/validation/controls.md).
Dated 0.2.0 maintenance notes are labeled separately.

Repair task vendored from Brikster/Chatty (base `c632a311`, fix `3c62096c`); the server
starts with a seeded `tests/seed/Chatty/chats.yml` that declares chat commands.

## Roles

- 170 cases: 2 `target` (server), 165 `preserved` (3 server + 161 upstream JUnit tests),
  1 `runtime-sentinel`, 2 `static`.

## Controls (real Paper 1.21.11 build 132, 2026-09-22, agent-authored scratch verifier)

| control | kind | what it is | result |
| --- | --- | --- | --- |
| `target-negative-register-only` | target-negative | register-only reload, never unregisters | fails only `server:renamed chat command drops its old name after chatty reload`; admissible |
| `compat-negative-no-startup-registration` | compat-negative | start-up registration dropped | fails only `server:chat commands declared at startup are registered`; admissible |
| `alternative-a` | alternative | independent diff-and-sync | 100; admissible |

Starter: exactly the two target cases fail (161/161 unit). Reference: 100 three times. Tamper
(GradleException in both build files, `ConstantsTest.java` deleted): verdict unchanged.
