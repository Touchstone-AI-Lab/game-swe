# Acceptance gates: chatty-reload-ignores-chat-commands

## 0.2.0 (catalog `rhenium-minecraft-v1` 0.2.0, 7 server cases)

### Offline evidence, 2026-11-02

Lab (Linux x86_64, Docker), task development image = `eclipse-temurin:21-jdk` with the task's
dependency cache warmed from the starter exactly like the verifier image, `--network=none`.
Each tree was synced and its frozen paths restored by `verify.py` itself, built offline, and
its upstream tests run; the grader suite was then compiled against GcbHarness, `paper-api`
1.21.11-R0.1-20260511.115010-91 and the built jar. No Paper server was started.

| Control | Tree | Offline build | Upstream unit cases | Suite compiles |
| --- | --- | --- | --- | --- |
| `starter` | starter, unchanged `environment/plugin` | passed | 161/161 pass | yes |
| `reference` | starter + `solution/after` | passed | 161/161 pass | yes |
| `target-negative-register-only` | target-negative, base starter + `target-negative-register-only.patch` | passed | 161/161 pass | yes |
| `compat-negative-no-startup-registration` | compat-negative, base starter + `compat-negative-no-startup-registration.patch` | passed | 161/161 pass | yes |
| `alternative-a` | alternative, base starter + `alternative-a` | passed | 161/161 pass | yes |

### Real-server gates — 2026-11-04

All required controls below completed through the Hub `full` profile on the real
Paper 1.21.11 build 132 server on Lab (Linux x86_64, Docker with networking disabled).
The operator explicitly recorded EULA acceptance, and `official-download` prepared
and verified the pinned runtime. Every execution used the final task image by
immutable ID, matching the current `tests/` build context. Every frozen case was
observed as pass or fail; the runtime sentinel passed in every control.

| Control | Run | Score | Full profile | Control verdict |
| --- | --- | --- | --- | --- |
| `starter` | `run-5a2056a7981a4a00` | 40 | complete | expected failure |
| `reference` | `run-2aea1f17ee2740b8` | 100 | complete | all cases pass |
| `target-negative-register-only` | `run-02f76284dc6346e7` | 40 | complete | expected failure |
| `compat-negative-no-startup-registration` | `run-8671c42f53204b23` | 40 | complete | expected failure |
| `alternative-a` | `run-c8a4a80f383f45e1` | 100 | complete | all cases pass |
| `reference-repeat-2` | `run-6144442f9afe4719` | 100 | complete | all cases pass |
| `reference-repeat-3` | `run-68fe25453705474d` | 100 | complete | all cases pass |
| `tamper` | `run-b09cd332c75842e1` | 100 | complete | all cases pass |

The unchanged starter fails an intended target while preserving its baseline
contracts. All three references and the alternative pass every case. Each target
negative fails an intended target without losing preserved cases; compatibility
negatives retain every target and violate a preserved contract. The tampered
reference passes after the verifier restores frozen build inputs and upstream
tests. The final controls are not borrowed from catalog 0.1.0 or an earlier image.

The offline table above records the original 2026-11-02 trees. Where a negative
was maintained during native acceptance, the current manifest and real-server
table here are the admission evidence. Earlier complete failures, preliminary
controls and execution records remain in separate operator-owned validation data
outside the repository; none was overwritten or silently reclassified.

<!-- 0.1.0 record below -->

## 0.1.0 record (historical, superseded by 0.2.0)

Real Paper 1.21.11 build 132 server, scratch verifier image
`gcb-scratch-chatty-reload-ignores-chat-commands` built from `tests/Dockerfile`
(base `gcb-minecraft-paper-verifier:1.21.11-132`), run with `--network=none
--cap-drop=ALL --cpus=4 --memory=8g` and the submission mounted read-only, 2026-09-22.
Every run was complete (offline `shadowJar`, 161 upstream JUnit cases, six server cases
all observed, `plugin data seeded from tests/seed: Chatty`); wall time 61–79 s per run.

| Control | Submission | Result | Failed cases |
| --- | --- | --- | --- |
| starter (`nop`) | `environment/plugin` unchanged | complete, not passed, 0 | `chat command added in chats.yml is registered by chatty reload` (`/gcbadd must be registered in the server command map …`), `renamed chat command drops its old name after chatty reload` (`/gcbworld must be registered …`) — both target |
| reference (`oracle`) ×3 | starter + `solution/after` | complete, passed, 1 three times; server log shows `Registered chat command /gcbadd`, `Unregistered chat command /gcbglobal`, `Registered chat command /gcbworld` | none |
| alternative | starter + an independent `syncChatCommands()` in `initialize()`/`onEnable` that diffs a name→(chat id, aliases) map, `deleteRootCommand`s stale entries, registers missing ones and resolves `ChatCommandHandler` from the current injector at execution time (`gates/alternative.patch`) | complete, passed, 1 | none |
| target-negative | register-only variant: `initialize()` registers commands whose name is not yet in a set, never unregisters (`gates/target-neg.patch`) | complete, not passed, 0 | `renamed chat command drops its old name after chatty reload` only (`/gcbglobal must no longer be registered … (was <…BukkitCommand(gcbglobal)>)`) |
| compat-negative | alternative fix with the start-up `registerChatCommands()` call dropped, so registration happens only inside `initialize()` where the sync command manager does not exist yet at start-up (`gates/compat-neg.patch`) | complete, not passed, 0 | `chat commands declared at startup are registered` only (server, preserved) |
| tamper | reference plus `throw new GradleException(...)` appended to `build.gradle` and `spigot/build.gradle`, and `spigot/src/test/java/ru/brikster/chatty/ConstantsTest.java` deleted | complete, passed, 1 (`frozen paths restored from the starter: build.gradle, settings.gradle, gradle, gradlew, gradlew.bat, api/build.gradle, spigot/build.gradle, spigot/src/test`; 161/161 unit cases observed; verdict equals oracle) | none |

Exploratory run before the gates (`explore/explore-base.log`, base jar, seeded `chats.yml`,
console commands): start-up logs `Registered chat command /gcblocal` and `/gcbglobal`; a
console dispatch of a chat command answers `TerminalConsoleCommandSender is not allowed to
execute that command. Must be of type Player`; after rewriting `chats.yml` (added `gcbadd`,
`global` renamed to `gcbworld`) and `chatty reload` (`Plugin successfully reloaded!`), `gcbadd`
and `gcbworld` are `Unknown or incomplete command` while `gcbglobal` still answers — the
symptom quoted in the exam.
