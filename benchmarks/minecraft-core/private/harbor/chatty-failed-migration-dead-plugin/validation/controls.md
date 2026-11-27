# Acceptance gates: chatty-failed-migration-dead-plugin

## 0.2.0 (catalog `rhenium-minecraft-v1` 0.2.0, 7 server cases)

### Offline evidence, 2026-11-02

Lab (Linux x86_64, Docker), task development image = `eclipse-temurin:21-jdk` with the task's
dependency cache warmed from the starter exactly like the verifier image, `--network=none`.
Each tree was synced and its frozen paths restored by `verify.py` itself, built offline, and
its upstream tests run; the grader suite was then compiled against GcbHarness, `paper-api`
1.21.11-R0.1-20260511.115010-91 and the built jar. No Paper server was started.

| Control | Tree | Offline build | Upstream unit cases | Suite compiles |
| --- | --- | --- | --- | --- |
| `starter` | starter, unchanged `environment/plugin` | passed | 54/54 pass | yes |
| `reference` | starter + `solution/after` | passed | 54/54 pass | yes |
| `target-negative-wipe-instead-of-quarantine` | target-negative, base starter + `target-negative-wipe-instead-of-quarantine.patch` | passed | 54/54 pass | yes |
| `target-negative-no-clamp` | target-negative, base reference + `target-negative-no-clamp.patch` | passed | 54/54 pass | yes |
| `compat-negative-backup-moved-into-quarantine` | compat-negative, base starter + `compat-negative-backup-moved-into-quarantine.patch` | passed | 54/54 pass | yes |
| `alternative-a` | alternative, base starter + `alternative-a` | passed | 54/54 pass | yes |

### Real-server gates — 2026-11-04

All required controls below completed through the Hub `full` profile on the real
Paper 1.21.11 build 132 server on Lab (Linux x86_64, Docker with networking disabled).
The operator explicitly recorded EULA acceptance, and `official-download` prepared
and verified the pinned runtime. Every execution used the final task image by
immutable ID, matching the current `tests/` build context. Every frozen case was
observed as pass or fail; the runtime sentinel passed in every control.

| Control | Run | Score | Full profile | Control verdict |
| --- | --- | --- | --- | --- |
| `starter` | `run-16a226c7eddc43e3` | 40 | complete | expected failure |
| `reference` | `run-3a95f63284cf4897` | 100 | complete | all cases pass |
| `target-negative-wipe-instead-of-quarantine` | `run-25ee92720bac417a` | 40 | complete | expected failure |
| `target-negative-no-clamp` | `run-a00f901e21464f7c` | 40 | complete | expected failure |
| `compat-negative-backup-moved-into-quarantine` | `run-e6849f17768c4d75` | 40 | complete | expected failure |
| `alternative-a` | `run-d0085f6382694110` | 100 | complete | all cases pass |
| `reference-repeat-2` | `run-dc37869b00274a33` | 100 | complete | all cases pass |
| `reference-repeat-3` | `run-ebe55007b084483a` | 100 | complete | all cases pass |
| `tamper` | `run-7d39fa81027b4e5c` | 100 | complete | all cases pass |

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

The initial compatibility negative (`run-61f8de2e60d64cdd`) lacked
the new caps-limit repair, so it failed a target in addition to its intended
backup-preservation regression. It now includes the unchanged reference migrator
repair and retains the deliberate backup relocation. Assertions and case roles
were not changed to admit it; the original failed record remains separate.

<!-- 0.1.0 record below -->

## 0.1.0 record (historical, superseded by 0.2.0)

Real Paper 1.21.11 build 132 server, scratch verifier image
`gcb-scratch-chatty-failed-migration-dead-plugin` built from `tests/Dockerfile`
(base `gcb-minecraft-paper-verifier:1.21.11-132`), run with `--network=none
--cap-drop=ALL --cpus=4 --memory=8g` and the submission mounted read-only, 2026-09-22.
Every run was complete (offline `shadowJar`, 54 upstream JUnit cases observed and passed,
six server cases all observed, `plugin data seeded from tests/seed: Chatty`); wall time
58–61 s per run.

| Control | Submission | Result | Failed cases |
| --- | --- | --- | --- |
| starter (`nop`) | `environment/plugin` unchanged | complete, not passed, 0 | exactly the three target cases: `chat pipeline is live after a failed migration` (`Chatty must have a listener registered for AsyncPlayerChatEvent …`), `failed migration is quarantined and reported` (`exactly one Chatty_failed_migration_<timestamp> folder must sit next to the data folder, got []`), `chatty reload works after a failed migration` (reply `Error while reloading plugin: CreationException. See console for more details.`) |
| reference (`oracle`) ×3 | starter + `solution/after` | complete, passed, 1 three times; server log shows `Failed to migrate the legacy configuration. Your v2 files are preserved in "Chatty_old_…"`, `The half-migrated configuration was moved to "Chatty_failed_migration_…"`, `Chatty started with a default configuration instead.` | none |
| alternative | starter + an independent `recoverFromFailedMigration()`/`tearDownQuietly()` pair in `Chatty.java` (SEVERE naming the backup folder, quiet teardown, move to `Chatty_failed_migration_<ts>`, `initialize()`, WARNING "started with a default configuration instead"; `closeResources()` made null-tolerant through local copies of the fields) (`gates/alternative.patch`) | complete, passed, 1 | none |
| target-negative | "start clean" variant: the alternative with the half-migrated folder deleted recursively instead of quarantined (`gates/target-neg.patch`); the plugin recovers and reloads, but the migrated output is gone | complete, not passed, 0 | `failed migration is quarantined and reported` only (`… got []`) |
| compat-negative | "tidy up" variant: the alternative that also moves the `Chatty_old_<ts>` backup into the quarantine folder (`gates/compat-neg.patch`), breaking the documented retry path | complete, not passed, 0 | `legacy configuration is moved aside before migrating` only (server, preserved; `exactly one Chatty_old_<timestamp> folder … got []`) |
| tamper | reference plus `throw new GradleException(...)` appended to `build.gradle` and `spigot/build.gradle`, and `spigot/src/test/java/ru/brikster/chatty/ConstantsTest.java` deleted (`gates/tamper-build.patch`) | complete, passed, 1 (`frozen paths restored from the starter: build.gradle, settings.gradle, gradle, gradlew, gradlew.bat, api/build.gradle, spigot/build.gradle, spigot/src/test`; 54/54 unit cases observed; verdict equals oracle) | none |

The first `nop`/`oracle` attempts failed to compile the grader (`RegisteredListener`
imported from `org.bukkit.event` instead of `org.bukkit.plugin`); the import was fixed, the
image rebuilt, and every gate above was run on the rebuilt image
(`gates/*.compile-failed.logs` keep the two aborted runs).

Pre-authoring evidence on the same server without the harness (`../../..` scratch
`evidence/`): the base jar with the seeded `config.yml` logs `Failed to migrate legacy
configuration — using defaults`, lists Chatty as enabled and answers `chatty reload` with
`Error while reloading plugin: CreationException`; the same file copied into a running
server's data folder is ignored by `chatty reload` (the reload path never migrates), which is
why the configuration is seeded before start-up.
