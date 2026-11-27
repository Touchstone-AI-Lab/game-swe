# Acceptance gates: betterteams-help-page-bounds

## 0.2.0 (catalog `rhenium-minecraft-v1` 0.2.0, 10 server cases)

### Offline evidence, 2026-11-02

Lab (Linux x86_64, Docker), task development image = `eclipse-temurin:21-jdk` with the task's
dependency cache warmed from the starter exactly like the verifier image, `--network=none`.
Each tree was synced and its frozen paths restored by `verify.py` itself, built offline, and
its upstream tests run; the grader suite was then compiled against GcbHarness, `paper-api`
1.21.11-R0.1-20260511.115010-91 and the built jar. No Paper server was started.

| Control | Tree | Offline build | Upstream unit cases | Suite compiles |
| --- | --- | --- | --- | --- |
| `starter` | starter, unchanged `environment/plugin` | passed | 44/44 pass | yes |
| `reference` | starter + `solution/after` | passed | 44/44 pass | yes |
| `target-negative-overflow-unclamped` | target-negative, base starter + `target-negative-overflow-unclamped.patch` | passed | 44/44 pass | yes |
| `target-negative-prefix-in-help-only` | target-negative, base starter + `target-negative-prefix-in-help-only.patch` | passed | 44/44 pass | yes |
| `compat-negative-prefix-on-single-help` | compat-negative, base starter + `compat-negative-prefix-on-single-help.patch` | passed | 44/44 pass | yes |
| `alternative-a` | alternative, base starter + `alternative-a` | passed | 44/44 pass | yes |

### Real-server gates — 2026-11-04

All required controls below completed through the Hub `full` profile on the real
Paper 1.21.11 build 132 server on Lab (Linux x86_64, Docker with networking disabled).
The operator explicitly recorded EULA acceptance, and `official-download` prepared
and verified the pinned runtime. Every execution used the final task image by
immutable ID, matching the current `tests/` build context. Every frozen case was
observed as pass or fail; the runtime sentinel passed in every control.

| Control | Run | Score | Full profile | Control verdict |
| --- | --- | --- | --- | --- |
| `starter` | `run-e66036422c434344` | 40 | complete | expected failure |
| `reference` | `run-8d4dcc4d11b84113` | 100 | complete | all cases pass |
| `target-negative-overflow-unclamped` | `run-13fee97465a542b8` | 40 | complete | expected failure |
| `target-negative-prefix-in-help-only` | `run-d59004c5dca84fdc` | 40 | complete | expected failure |
| `compat-negative-prefix-on-single-help` | `run-5610bcda97c04a62` | 40 | complete | expected failure |
| `alternative-a` | `run-ad42b0f444924976` | 100 | complete | all cases pass |
| `reference-repeat-2` | `run-c345d209a4d345f9` | 100 | complete | all cases pass |
| `reference-repeat-3` | `run-f30bb1946c974dce` | 100 | complete | all cases pass |
| `tamper` | `run-cb14f2228f8c4472` | 100 | complete | all cases pass |

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

Real Paper 1.21.11 build 132 server, verifier image `gcb-scratch-betterteams-help-page-bounds`
built from this task's `tests/` on top of `gcb-minecraft-paper-verifier:1.21.11-132` (Apache
Maven 3.9.11 installed, dependency cache warmed online once: 376 s), every run with
`--network=none --cap-drop=ALL --cpus=4 --memory=8g`, 2026-09-22. Every run was complete (offline
`mvn -o -pl BetterTeams -am package`, 44 upstream JUnit cases read from
`BetterTeams/target/surefire-reports`, eight server cases all observed); wall time 37–45 s per run.

| Control | Submission | Result | Failed cases |
| --- | --- | --- | --- |
| starter (`nop`) | `environment/plugin` unchanged | complete, not passed, reward 0 | `help entries carry the plugin prefix` (`null/team delhome - ...`), `page zero and negative pages fall back to the first page` (internal-error line after the header), `pages past the end show the last page` (footer `Page 7/6`) — the three target cases, nothing else |
| reference (`oracle`) ×3 | starter + `solution/after` | complete, passed, reward 1 three times | none |
| alternative | starter + one-place clamp of the requested page into `[1, maxPage]` in `getPage` and `getPrefix()` reading `prefixFormat` from the plugin config | complete, passed, reward 1 | none |
| target-negative | prefix repaired and `page < 1` clamped, but `page > maxPage` still returns `maxPage` | complete, not passed, reward 0 | `pages past the end show the last page` only |
| compat-negative | reference repair plus the prefix also prepended to the single-command help line (`createHelpMessage`) | complete, not passed, reward 0 | `help for one command is unchanged` only (`[BetterTeams] /team create ...`) |
| tamper | reference plus `THIS IS NOT XML` appended to `BetterTeams/pom.xml` and `ExtUtilTest.java` deleted | complete, passed, reward 1 (verifier log: frozen paths restored — root, module and extension `pom.xml`, `BetterTeams/src/test`; 44/44 unit cases observed) | none |

The alternative and negative sources are kept as diffs against the starter next to the scratch
pack (`gates/alternative.diff`, `gates/target-neg.diff`, `gates/compat-neg.diff`, `gates/tamper.diff`).
