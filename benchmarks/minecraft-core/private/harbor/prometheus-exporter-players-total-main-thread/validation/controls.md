# Acceptance gates: prometheus-exporter-players-total-main-thread

## 0.2.0 (catalog `rhenium-minecraft-v1` 0.2.0, 7 server cases)

### Offline evidence, 2026-11-02

Lab (Linux x86_64, Docker), task development image = `eclipse-temurin:21-jdk` with the task's
dependency cache warmed from the starter exactly like the verifier image, `--network=none`.
Each tree was synced and its frozen paths restored by `verify.py` itself, built offline, and
its upstream tests run; the grader suite was then compiled against GcbHarness, `paper-api`
1.21.11-R0.1-20260511.115010-91 and the built jar. No Paper server was started.

| Control | Tree | Offline build | Upstream unit cases | Suite compiles |
| --- | --- | --- | --- | --- |
| `starter` | starter, unchanged `environment/plugin` | passed | 27/27 pass | yes |
| `reference` | starter + `solution/after` | passed | 27/27 pass | yes |
| `target-negative-sync-playerdata-count` | target-negative, base starter + `target-negative-sync-playerdata-count.patch` | passed | 27/27 pass | yes |
| `compat-negative-online-only` | compat-negative, base starter + `compat-negative-online-only.patch` | passed | 27/27 pass | yes |
| `compat-negative-everything-async` | compat-negative, base starter + `compat-negative-everything-async.patch` | passed | 27/27 pass | yes |
| `compat-negative-villagers-async` | compat-negative, base reference + `compat-negative-villagers-async.patch` | passed | 27/27 pass | yes |
| `alternative-a` | alternative, base starter + `alternative-a` | passed | 27/27 pass | yes |

### Real-server gates — 2026-11-04

All required controls below completed through the Hub `full` profile on the real
Paper 1.21.11 build 132 server on Lab (Linux x86_64, Docker with networking disabled).
The operator explicitly recorded EULA acceptance, and `official-download` prepared
and verified the pinned runtime. Every execution used the final task image by
immutable ID, matching the current `tests/` build context. Every frozen case was
observed as pass or fail; the runtime sentinel passed in every control.

| Control | Run | Score | Full profile | Control verdict |
| --- | --- | --- | --- | --- |
| `starter` | `run-342177f3b8b9466c` | 40 | complete | expected failure |
| `reference` | `run-12600ce51a9c4650` | 100 | complete | all cases pass |
| `target-negative-sync-playerdata-count` | `run-77d2116e4a2d4ee1` | 40 | complete | expected failure |
| `compat-negative-online-only` | `run-6d024e90bcd645bb` | 40 | complete | expected failure |
| `compat-negative-everything-async` | `run-712c7ab47fb54ebf` | 40 | complete | expected failure |
| `compat-negative-villagers-async` | `run-8319b66421674816` | 40 | complete | expected failure |
| `alternative-a` | `run-b80c58f5c7f4411c` | 100 | complete | all cases pass |
| `reference-repeat-2` | `run-d997446fc3e74c38` | 100 | complete | all cases pass |
| `reference-repeat-3` | `run-f0e86b9c31434d29` | 100 | complete | all cases pass |
| `tamper` | `run-5410d48f37a04e9c` | 100 | complete | all cases pass |

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

Real Paper 1.21.11 build 132 server, verifier image `gcb-scratch-prometheus-exporter-players-total-main-thread`
built from `tests/Dockerfile` on the pinned `gcb-minecraft-paper-verifier:1.21.11-132` base (digest
`d74e0fad…`, the 2026-09-22 rebuild), run through `tests/test.sh` with `--network=none --cap-drop=ALL
--security-opt=no-new-privileges:true --cpus=4 --memory=8g`, 2026-09-22. Every run was complete (offline Maven
`package`, 27 frozen upstream unit cases and five server cases all observed); wall time 41–50 s per run.

| Control | Submission | Result | Failed cases |
| --- | --- | --- | --- |
| starter (`nop`) | `environment/plugin` unchanged | complete, not passed, reward 0 | `players_total is collected without the main thread` (timeout after 3 s: the collection waits for a main-thread task), `scrape completes while the main thread is busy` (5 s request timeout) — both target |
| reference (`oracle`) ×3 | starter + `solution/after` | complete, passed, reward 1 three times | none |
| alternative | `PlayersTotal` overrides `collect()` itself: `CompletableFuture.runAsync` around `doCollect()`, never touching the scheduler (`isAsyncCapable` untouched) | complete, passed, reward 1 | none |
| target-negative | "cure the lag" by counting `playerdata/*.dat` files directly instead of materialising `OfflinePlayer`s, still collected through the main-thread task | complete, not passed, reward 0 | the two target cases only |
| compat-negative | `isAsyncCapable() = true` but the gauge counts `Bukkit.getOnlinePlayers().size()` | complete, not passed, reward 0 | `players_total reports every known player` (expected 3, got 0.0) only |
| tamper | reference plus a `<broken>` tag appended to `pom.xml`, `TpsCollectorTest.java` deleted and the expected value in `PrometheusExporterTest` changed to `tampered` | complete, passed, reward 1 (frozen `pom.xml` and `src/test` restored, verdict unchanged) | none |

Rejected negative kept as evidence (`gates/target-neg-rejected-stale-cache.*` in the authoring scratch):
a wrong fix that caches `getOfflinePlayers().length` from an async repeating task every 20 ticks and
keeps the collection synchronous fails both target cases but also the preserved count case (stale
cache: `mc_players_total` 0.0 against 3 playerdata files added in the tick before the scrape), so it
is not a target-only negative.

Unit layer: the surefire XML at the base commit lists 32 executions, 27 distinct identities;
`PathFileSizeTest$WhenPathIsFile.returnsFileSize` is a `@RepeatedTest(5)` and is unobservable
through JUnit identities, so it is not frozen. Every run observed exactly 27/27.

Earlier suite iteration on the same image: the first sentinel/preserved versions used
`getInt("port", 0)` (bypasses Bukkit config defaults, which is where this plugin keeps `port`) and
appended `" "`/`"{"` to labelled sample names; both were grader bugs, fixed before the runs above.
The two target cases failed on the starter and passed on the reference already in that first run.

Confirmation on the final image (regenerated `tests/Dockerfile` from the repository's materialize.py,
same Maven 3.9.11 release and SHA-512): starter complete, reward 0, exactly the two target cases fail;
reference complete, reward 1.
