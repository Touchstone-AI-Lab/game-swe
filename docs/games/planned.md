# Planned game integrations

This page records ownership before implementation starts. Planned entries do not
claim that the game, mod loader, dedicated server, or evaluator currently works
with GameCodeBench.

Before moving a game to `In Development`, its maintainers must pin the target
game/API version, benchmark-runner platforms, submission language, evaluator
toolchain, and the first end-to-end task.

## Slay the Spire

| Field | Planning value |
| --- | --- |
| Maintainer | Changyi |
| Status | `Planned` |
| Proposed plugin ID | `slay-the-spire` |
| Expected submission language | Java |
| Required decision | Pin the game version, modding API/toolchain, runner platforms, and evaluation boundary. |

The [Slay the Spire pack](../../benchmarks/slay-the-spire-core/README.md) contains ten tasks and is registered with the Hub. Three standalone tasks run through its JDK 8 container evaluator without the game. Seven native-runtime tasks run in the licensed game, which the Hub downloads from Steam with the operator's own account (or an operator supplies to the manual Harbor workflow). See the [current support matrix](slay-the-spire.md).
