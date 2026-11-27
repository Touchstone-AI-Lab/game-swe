# Acceptance gates: chatty-reload-leaks-threads

## 0.2.0 (catalog `rhenium-minecraft-v1` 0.2.0, 8 server cases)

### Offline evidence, 2026-11-02

Lab (Linux x86_64, Docker), task development image = `eclipse-temurin:21-jdk` with the task's
dependency cache warmed from the starter exactly like the verifier image, `--network=none`.
Each tree was synced and its frozen paths restored by `verify.py` itself, built offline, and
its upstream tests run; the grader suite was then compiled against GcbHarness, `paper-api`
1.21.11-R0.1-20260511.115010-91 and the built jar. No Paper server was started.

| Control | Tree | Offline build | Upstream unit cases | Suite compiles |
| --- | --- | --- | --- | --- |
| `starter` | starter, unchanged `environment/plugin` | passed | 82/82 pass | yes |
| `reference` | starter + `solution/after` | passed | 82/82 pass | yes |
| `target-negative-ticker-only` | target-negative, base starter + `target-negative-ticker-only.patch` | passed | 82/82 pass | yes |
| `target-negative-executor-not-shut-down` | target-negative, base starter + `target-negative-executor-not-shut-down.patch` | passed | 82/82 pass | yes |
| `target-negative-no-null-guard` | target-negative, base starter + `target-negative-no-null-guard.patch` | passed | 82/82 pass | yes |
| `target-negative-recreate-only` | target-negative, base reference + `target-negative-recreate-only.patch` | passed | 82/82 pass | yes |
| `compat-negative-metrics-kept-forever` | compat-negative, base starter + `compat-negative-metrics-kept-forever.patch` | passed | 82/82 pass | yes |
| `alternative-a` | alternative, base starter + `alternative-a` | passed | 82/82 pass | yes |

### Real-server gates — 2026-11-04

All required controls below completed through the Hub `full` profile on the real
Paper 1.21.11 build 132 server on Lab (Linux x86_64, Docker with networking disabled).
The operator explicitly recorded EULA acceptance, and `official-download` prepared
and verified the pinned runtime. Every execution used the final task image by
immutable ID, matching the current `tests/` build context. Every frozen case was
observed as pass or fail; the runtime sentinel passed in every control.

| Control | Run | Score | Full profile | Control verdict |
| --- | --- | --- | --- | --- |
| `starter` | `run-e3fbdb3d1b674079` | 40 | complete | expected failure |
| `reference` | `run-ecba636d054f476b` | 100 | complete | all cases pass |
| `target-negative-ticker-only` | `run-0f5d2d45289d4b21` | 40 | complete | expected failure |
| `target-negative-executor-not-shut-down` | `run-1e0bad8780f04cad` | 40 | complete | expected failure |
| `target-negative-no-null-guard` | `run-553c9f99d517470a` | 40 | complete | expected failure |
| `target-negative-recreate-only` | `run-b4061190be6440c4` | 40 | complete | expected failure |
| `compat-negative-metrics-kept-forever` | `run-c42221eb72104a60` | 40 | complete | expected failure |
| `alternative-a` | `run-c9b0d48059e247de` | 100 | complete | all cases pass |
| `reference-repeat-2` | `run-59e792a91b644c46` | 100 | complete | all cases pass |
| `reference-repeat-3` | `run-72702232a424432d` | 100 | complete | all cases pass |
| `tamper` | `run-ff8d11d723bf4619` | 100 | complete | all cases pass |

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

Real Paper 1.21.11 build 132 server, verifier image `gcb-scratch-chatty-reload-leaks-threads`
built from `tests/Dockerfile` on top of `gcb-minecraft-paper-verifier:1.21.11-132`, run with
`--network=none --cap-drop=ALL --cpus=4 --memory=8g` through `tests/test.sh`, 2026-09-22.
Every run was complete (offline `shadowJar` build, 82 upstream JUnit cases, seven server
cases all observed); wall time 81–103 s per run with eight runs in parallel on the host.
Ticked cases took 81 / 41 / 131 / 201 ticks (`notifications keep ticking`, `bStats metrics
stay scheduled`, `previous ticker is stopped`, `reloads do not leak`) in every run.

| Control | Submission | Result | Failed cases |
| --- | --- | --- | --- |
| starter (`nop`) | `environment/plugin` unchanged | complete, not passed, 0 | `previous ticker is stopped by a reload` (`Executors$DelegatedScheduledExecutorService ... is still accepting work`), `cancelling a ticker that never started does not throw` (`NullPointerException: Cannot invoke "ScheduledFuture.cancel(boolean)" because "this.future" is null`), `reloads do not leak ticker or bStats threads` (`3 reloads left 6 extra plugin-owned thread(s) alive: new [bStats-Metrics ×3, pool-24-thread-1, pool-25-thread-1, pool-26-thread-1], gone []`) — exactly the three targets |
| reference (`oracle`) ×3 | starter + `solution/after` | complete, passed, 1 three times | none |
| alternative | starter + independent fix (`gates/alternative.patch`): the ticker creates its executor lazily in `startTicking()` with a named daemon factory (`Chatty notification ticker`) and `cancelTicking()` shuts it down and drops it; `MetricsSender.run()` returns the started `Metrics` and `Chatty` keeps it in a field that `closeResources()` shuts down; `ProxyServiceImpl` keeps and shuts down its Redisson client | complete, passed, 1 | none |
| target-negative A | reference ticker only; bStats and Redisson untouched (`gates/target-neg-a.patch`) | complete, not passed, 0 | `reloads do not leak ticker or bStats threads` only (`3 extra ... new [bStats-Metrics ×3, pool-26-thread-1], gone [pool-23-thread-1]`) |
| target-negative B | reference bStats/Redisson/`Chatty` changes plus a null-guarded `cancelTicking()` that still only cancels the future (`gates/target-neg-b.patch`) | complete, not passed, 0 | `previous ticker is stopped by a reload` and `reloads do not leak ticker or bStats threads` (`new [bStats-Metrics, pool-24/25/26-thread-1], gone [bStats-Metrics]`) — both targets, no preserved case |
| target-negative C | reference fix with the null guard removed: `future.cancel(false); future = null; executor.shutdownNow();` (`gates/target-neg-c.patch`) | complete, not passed, 0 | `cancelling a ticker that never started does not throw` only |
| compat-negative | reference ticker and Redisson changes, but bStats "fixed" by keeping the first `Metrics` instance forever (`if (activeMetrics != null) return;`, no shutdown in `closeResources()`) (`gates/compat-neg.patch`) | complete, not passed, 0 | `bStats metrics stay scheduled after a reload` (preserved; `plugin threads: [Notification Thread, pool-19-thread-1]`); no target case failed |
| tamper | reference plus `throw new GradleException("tampered build file")` appended to `spigot/build.gradle` and `spigot/src/test/.../ActionbarNotificationSoundTest.java` deleted (`gates/tamper.patch`) | complete, passed, 1 (`frozen paths restored from the starter: build.gradle, settings.gradle, gradle, gradlew, gradlew.bat, api/build.gradle, spigot/build.gradle, spigot/src/test`; 82/82 unit cases; verdict unchanged) | none |

Observed thread names: the JDK's own `Notification Thread` (JMX) matches the `notification`
keyword and is present in every snapshot; it is steady-state, so the before/after delta ignores
it. On the starter the reloads of the earlier cases had already left `pool-11/17/18/19/20/21/23-thread-1`
and four `bStats-Metrics` threads behind before the leak case started. No gate needed a second
iteration of the suite or the exam.
