# Acceptance gates: chatty-v2-migration-null-spy-format

## 0.2.0 (catalog `rhenium-minecraft-v1` 0.2.0, 11 server cases)

### Offline evidence, 2026-11-02

Lab (Linux x86_64, Docker), task development image = `eclipse-temurin:21-jdk` with the task's
dependency cache warmed from the starter exactly like the verifier image, `--network=none`.
Each tree was synced and its frozen paths restored by `verify.py` itself, built offline, and
its upstream tests run; the grader suite was then compiled against GcbHarness, `paper-api`
1.21.11-R0.1-20260511.115010-91 and the built jar. No Paper server was started.

| Control | Tree | Offline build | Upstream unit cases | Suite compiles |
| --- | --- | --- | --- | --- |
| `starter` | starter, unchanged `environment/plugin` | passed | 48/48 pass | yes |
| `reference` | starter + `solution/after` | passed | 48/48 pass | yes |
| `target-negative-migrator-only` | target-negative, base starter + `target-negative-migrator-only.patch` | passed | 48/48 pass | yes |
| `target-negative-loader-guard-only` | target-negative, base starter + `target-negative-loader-guard-only.patch` | passed | 48/48 pass | yes |
| `target-negative-locale-migrator-only` | target-negative, base reference + `target-negative-locale-migrator-only.patch` | passed | 48/48 pass | yes |
| `compat-negative-ignore-explicit-format` | compat-negative, base starter + `compat-negative-ignore-explicit-format.patch` | passed | 48/48 pass | yes |
| `alternative-a` | alternative, base starter + `alternative-a` | passed | 48/48 pass | yes |

### Real-server gates — 2026-11-04

All required controls below completed through the Hub `full` profile on the real
Paper 1.21.11 build 132 server on Lab (Linux x86_64, Docker with networking disabled).
The operator explicitly recorded EULA acceptance, and `official-download` prepared
and verified the pinned runtime. Every execution used the final task image by
immutable ID, matching the current `tests/` build context. Every frozen case was
observed as pass or fail; the runtime sentinel passed in every control.

| Control | Run | Score | Full profile | Control verdict |
| --- | --- | --- | --- | --- |
| `starter` | `run-7269dfe7ce754a18` | 40 | complete | expected failure |
| `reference` | `run-305772fa0dc74313` | 100 | complete | all cases pass |
| `target-negative-migrator-only` | `run-4516d2d9ba3c4c0c` | 40 | complete | expected failure |
| `target-negative-loader-guard-only` | `run-7fc2f86fc0a94311` | 40 | complete | expected failure |
| `target-negative-locale-migrator-only` | `run-a314f12fe0574407` | 40 | complete | expected failure |
| `compat-negative-ignore-explicit-format` | `run-e933e0206d2e4bc2` | 40 | complete | expected failure |
| `alternative-a` | `run-e8053a41af23469f` | 100 | complete | all cases pass |
| `reference-repeat-2` | `run-7c23a051c2784c1e` | 100 | complete | all cases pass |
| `reference-repeat-3` | `run-9c978dc3585f4470` | 100 | complete | all cases pass |
| `tamper` | `run-282ae613a79340ff` | 100 | complete | all cases pass |

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

The initial compatibility negative (`run-7626d76768e84161`) lacked
the new locale repairs. It now starts from the current reference and changes only
the spy component to use a derived default instead of the configured explicit
format. Every locale repair remains present. Assertions and case roles are
unchanged, and the initial failed record remains separate.

<!-- 0.1.0 record below -->

## 0.1.0 record (historical, superseded by 0.2.0)

Real Paper 1.21.11 build 132 server, scratch verifier image
`gcb-scratch-chatty-v2-migration-null-spy-format` built from `tests/Dockerfile`
(base `gcb-minecraft-paper-verifier:1.21.11-132`), run with `--network=none
--cap-drop=ALL --cpus=4 --memory=8g` and the submission mounted read-only, 2026-09-22.
Every run was complete (offline `shadowJar`, 48 upstream JUnit cases, seven server cases
all observed, `plugin data seeded from tests/seed: Chatty`); wall time 57–74 s per run.

| Control | Submission | Result | Failed cases |
| --- | --- | --- | --- |
| starter (`nop`) | `environment/plugin` unchanged | complete, not passed, 0 | exactly the four target cases: `chats from the legacy config are registered at start-up` (`chat "gcbstaff" must be registered …, got [global, local]`), `migrated chats carry a spy format` (`spy.format … got null`), `chatty reload succeeds on the migrated configuration` and `spy section with only enable reloads` (both `Error while reloading plugin: ProvisionException`) |
| reference (`oracle`) ×3 | starter + `solution/after` | complete, passed, 1 three times; server log shows the migration completing (`chat "gcbretired" was disabled in v2 and was not migrated`) with no `Failed to migrate` / `Error while reloading` | none |
| alternative | starter + an independent fix: `V2ConfigMigrator.spyFormatFor()` falls back to v2's default template and to the v3 default chat format, `ConfigsLoader.spyFormat()` converts a null spy format as `""`; `ChatsConfig` untouched (`gates/alternative.patch`) | complete, passed, 1 | none |
| target-negative | migrator-only fix (the alternative's migrator change, loader untouched) (`gates/target-neg.patch`) | complete, not passed, 0 | `spy section with only enable reloads` only |
| target-negative 2 | loader-guard-only fix (the alternative's loader change, migrator untouched) (`gates/target-neg-2.patch`) | complete, not passed, 0 | `migrated chats carry a spy format` (`spy.format … got null`) and `chatty reload succeeds on the migrated configuration` (the global chat's spy format renders empty after the reload) — both assert the migrated spy format, before and after a reload |
| compat-negative | migrator fix plus a loader that always derives the spy line from the chat format and ignores `spy.format` (`gates/compat-neg.patch`) | complete, not passed, 0 | `explicit spy formats survive a reload` only (server, preserved: `got [Spy] [GCB Local] {player}: {message}` instead of `[Watch local]`) |
| tamper | reference plus `throw new GradleException(...)` appended to `build.gradle` and `spigot/build.gradle`, and `spigot/src/test/java/ru/brikster/chatty/ConstantsTest.java` deleted | complete, passed, 1 (`frozen paths restored from the starter: build.gradle, settings.gradle, gradle, gradlew, gradlew.bat, api/build.gradle, spigot/build.gradle, spigot/src/test`; 48/48 unit cases observed; verdict equals oracle) | none |

Exploratory run before the gates (scratch `explore/explore-base.log`, base jar, the same seeded
v2 `config.yml`, console commands, no harness): the enable logs `Failed to migrate legacy
configuration — using defaults` with `ProvisionException … NullPointerException: input` from
`ConfigsLoader.loadChannels`; the migrated `chats.yml` carries `spy.format: null` for every
chat; `/chatty` answers; `chatty reload` on the migrated files and on a `chats.yml` whose chat
has `spy: {enable: true}` only both answer `Error while reloading plugin: ProvisionException`;
a fully explicit `chats.yml` reloads with `Plugin successfully reloaded!` — the symptom quoted
in the exam and the reason the preserved cases hold on the starter.
