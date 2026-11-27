# Acceptance gates: chatty-bad-channel-disables-plugin

## 0.2.0 (catalog `rhenium-minecraft-v1` 0.2.0, 11 server cases)

### Offline evidence, 2026-11-02

Lab (Linux x86_64, Docker), task development image = `eclipse-temurin:21-jdk` with the task's
dependency cache warmed from the starter exactly like the verifier image, `--network=none`.
Each tree was synced and its frozen paths restored by `verify.py` itself, built offline, and
its upstream tests run; the grader suite was then compiled against GcbHarness, `paper-api`
1.21.11-R0.1-20260511.115010-91 and the built jar. No Paper server was started.

| Control | Tree | Offline build | Upstream unit cases | Suite compiles |
| --- | --- | --- | --- | --- |
| `starter` | starter, unchanged `environment/plugin` | passed | 138/138 pass | yes |
| `reference` | starter + `solution/after` | passed | 138/138 pass | yes |
| `target-negative-unnamed-warning` | target-negative, base starter + `target-negative-unnamed-warning.patch` | passed | 138/138 pass | yes |
| `target-negative-whole-loop` | target-negative, base starter + `target-negative-whole-loop.patch` | passed | 138/138 pass | yes |
| `compat-negative-stay-equals-period` | compat-negative, base starter + `compat-negative-stay-equals-period.patch` | passed | 138/138 pass | yes |
| `alternative-a` | alternative, base starter + `alternative-a` | passed | 138/138 pass | yes |

### Real-server gates — 2026-11-04

All required controls below completed through the Hub `full` profile on the real
Paper 1.21.11 build 132 server on Lab (Linux x86_64, Docker with networking disabled).
The operator explicitly recorded EULA acceptance, and `official-download` prepared
and verified the pinned runtime. Every execution used the final task image by
immutable ID, matching the current `tests/` build context. Every frozen case was
observed as pass or fail; the runtime sentinel passed in every control.

| Control | Run | Score | Full profile | Control verdict |
| --- | --- | --- | --- | --- |
| `starter` | `run-330f77bf76d744fe` | 40 | complete | expected failure |
| `reference` | `run-29d6c43786654bba` | 100 | complete | all cases pass |
| `target-negative-unnamed-warning` | `run-2a3ee22bb05646db` | 40 | complete | expected failure |
| `target-negative-whole-loop` | `run-ea76a05524eb40a2` | 40 | complete | expected failure |
| `compat-negative-player-only-info` | `run-5f685d892d1147a8` | 40 | complete | expected failure |
| `alternative-a` | `run-09579719a9d74396` | 100 | complete | all cases pass |
| `reference-repeat-2` | `run-7c82669878b540d5` | 100 | complete | all cases pass |
| `reference-repeat-3` | `run-97768a76a3484202` | 100 | complete | all cases pass |
| `tamper` | `run-e433d9e6585540be` | 100 | complete | all cases pass |

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

The initial starter (`run-ba49f7c94767424d`) and reference
(`run-af8b6f1000b44132`) exposed a fixture error: adding a ticking chat channel
replaced the chat map without its default entry. Both input strings now explicitly
include that default; all notification assertions are unchanged. The earlier
`stay >= period` compatibility control also broke the target's valid middle
channel, so the current negative instead isolates loss of console information
output. Its original patch and failed records remain historical evidence.

<!-- 0.1.0 record below -->

## 0.1.0 record (historical, superseded by 0.2.0)

Real Paper 1.21.11 build 132 server, verifier image `gcb-scratch-chatty-bad-channel-disables-plugin`
built from `tests/Dockerfile` on top of `gcb-minecraft-paper-verifier:1.21.11-132`, run with
`--network=none --cap-drop=ALL --cpus=4 --memory=8g` through `tests/test.sh`, 2026-09-22.
Every run was complete (offline `shadowJar` build, 138 upstream JUnit cases, seven server
cases all observed); wall time 71–77 s per run with nine runs in parallel on the host.
The verifier used the module-aware JUnit report discovery (`**/build/test-results/**/*.xml`),
see `NOTES.md` "Build".

| Control | Submission | Result | Failed cases |
| --- | --- | --- | --- |
| starter (`nop`) | `environment/plugin` unchanged | complete, not passed, 0 | `reload survives an action bar channel whose stay exceeds its period` (`/chatty reload` answered `Error while reloading plugin: ProvisionException`; console trace `Guice/ErrorInjectingMethod: IllegalArgumentException: Stay should be equal or lower than period`), `skipped channel is reported by name` (only `Error while reloading Chatty` warnings) — both target |
| reference (`oracle`) ×3 | starter + `solution/after` | complete, passed, 1 three times; console `WARN [ru.brikster.chatty.guice.ConfigsLoader] Skipping the "gcb_broken" action bar notification from notifications.yml: Stay should be equal or lower than period` | none |
| alternative | starter + `ConfigsLoader` rewritten with explicit `stay > period` validation for action bar channels and a `Callable`-based `register` helper that reports through `plugin.getLogger()` (`gates/alternative.patch`) | complete, passed, 1 | none |
| target-negative A | per-channel `try/catch` that logs only the exception message, never the channel id (`gates/target-neg-a.patch`) | complete, not passed, 0 | `skipped channel is reported by name` only |
| target-negative B | `try/catch` around each section's whole `forEach` (`gates/target-neg-b.patch`) | complete, not passed, 0 | `reload survives an action bar channel whose stay exceeds its period` (`gcb_healthy`, listed after the bad channel, missing) and `skipped channel is reported by name` — both target |
| compat-negative | alternative fix with the boundary wrong: skips channels whose `stay >= period` (`gates/compat-neg.patch`) | complete, not passed, 0 | `default configuration reloads cleanly` (shipped action bar `default` has `stay == period`) and `valid notifications.yml loads every channel` (`gcb_edge`) — both preserved; no target case failed |
| tamper | reference plus `throw new GradleException("tampered build file")` appended to `spigot/build.gradle` and `spigot/src/test/.../ActionbarNotificationSoundTest.java` deleted | complete, passed, 1 (`frozen paths restored from the starter: build.gradle, settings.gradle, gradle, gradlew, gradlew.bat, api/build.gradle, spigot/build.gradle, spigot/src/test`; 138/138 unit cases; verdict unchanged) | none |

Earlier iteration (`gates/*-with-enable-case.logs`): an eighth case that disabled and re-enabled
Chatty through `PluginManager` to reproduce the start-up failure was dropped because Paper
1.21.11 closes the plugin's jar classloader on disable, so `enablePlugin` failed for the
reference fix as well (`IllegalStateException: The plugin classloader for Chatty has thrown a
zip file error ... zip file closed`). The starter run of that iteration still failed exactly the
target cases.
