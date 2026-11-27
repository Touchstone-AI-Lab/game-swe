# Acceptance gates: multiverse-core-case-insensitive-world-names

## 0.2.0 (catalog `rhenium-minecraft-v1` 0.2.0, 10 server cases)

### Offline evidence, 2026-11-02

Lab (Linux x86_64, Docker), task development image = `eclipse-temurin:21-jdk` with the task's
dependency cache warmed from the starter exactly like the verifier image, `--network=none`.
Each tree was synced and its frozen paths restored by `verify.py` itself, built offline, and
its upstream tests run; the grader suite was then compiled against GcbHarness, `paper-api`
1.21.11-R0.1-20260511.115010-91 and the built jar. No Paper server was started.

| Control | Tree | Offline build | Upstream unit cases | Suite compiles |
| --- | --- | --- | --- | --- |
| `starter` | starter, unchanged `environment/plugin` | passed | 162/162 pass | yes |
| `reference` | starter + `solution/after` | passed | 162/162 pass | yes |
| `target-negative-remove-still-leaks` | target-negative, base starter + `target-negative-remove-still-leaks.patch` | passed | 162/162 pass | yes |
| `compat-negative-case-sensitive-lookups` | compat-negative, base starter + `compat-negative-case-sensitive-lookups.patch` | passed | 160/162: fails `Get world is case insensitive()` and `Create world failed - world exists and loaded (case insensitive)()` by design | yes |
| `alternative-a` | alternative, base starter + `alternative-a` | passed | 162/162 pass | yes |

### Real-server gates — 2026-11-04

All required controls below completed through the Hub `full` profile on the real
Paper 1.21.11 build 132 server on Lab (Linux x86_64, Docker with networking disabled).
The operator explicitly recorded EULA acceptance, and `official-download` prepared
and verified the pinned runtime. Every execution used the final task image by
immutable ID, matching the current `tests/` build context. Every frozen case was
observed as pass or fail; the runtime sentinel passed in every control.

| Control | Run | Score | Full profile | Control verdict |
| --- | --- | --- | --- | --- |
| `starter` | `run-cd99c47a62ae4d00` | 40 | complete | expected failure |
| `reference` | `run-93a7c9950ec24f10` | 100 | complete | all cases pass |
| `target-negative-remove-still-leaks` | `run-fa14dfa3b54c4dd7` | 40 | complete | expected failure |
| `compat-negative-case-sensitive-lookups` | `run-d9f1398bd7fa4331` | 10 | complete | expected failure |
| `alternative-a` | `run-9cf963f7eb964693` | 100 | complete | all cases pass |
| `reference-repeat-2` | `run-69ef24f7cd484b28` | 100 | complete | all cases pass |
| `reference-repeat-3` | `run-1b16169da1a84f87` | 100 | complete | all cases pass |
| `tamper` | `run-477c0be94545468e` | 100 | complete | all cases pass |

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

Real Paper 1.21.11 build 132 server, verifier image built by
`rhenium runtime prepare minecraft/paper-1.21.11-132`, `rhenium run … --profile full`,
2026-09-22. Every run was complete (build, 162 upstream unit cases, five server cases
all observed); wall time 100–120 s per run.

| Control | Submission | Result | Failed cases |
| --- | --- | --- | --- |
| starter (`nop`) | `environment/plugin` unchanged | complete, not passed, 40/100 | `mixed-case world can be unloaded`, `mixed-case world can be removed` (both target) |
| reference (`oracle`) ×3 | starter + `solution/after` | complete, passed, 100/100 three times | none |
| alternative | starter + lower-casing at the two removal sites and the unload lookup (`HashMap` kept) | complete, passed, 100/100 | none |
| target-negative | alternative fix minus the `worldsMap.remove` lower-casing | complete, not passed, 40/100 | `mixed-case world can be removed` only |
| compat-negative | every lower-casing in `WorldManager` removed (raw keys everywhere) | complete, not passed, 10/100 | `world lookups ignore case` (server, preserved) plus the two upstream unit tests `Get world is case insensitive()` and `Create world failed - world exists and loaded (case insensitive)()` |
| tamper | reference plus `throw new GradleException(...)` appended to `build.gradle` and `WorldManagerTest.kt` deleted | complete, passed, 100/100 (frozen paths restored, verdict unchanged) | none |

Earlier infrastructure controls on the same image family: a synthetic javac plugin scored
exactly its designed 2/3 cases, and a candidate that printed a forged `MINECRAFT_RESULT`
envelope and force-stopped the server was rejected (`expected exactly one harness payload,
saw 2`, incomplete).
