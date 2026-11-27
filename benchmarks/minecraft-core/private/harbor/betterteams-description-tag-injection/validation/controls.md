# Acceptance gates: betterteams-description-tag-injection

## 0.2.0 (catalog `rhenium-minecraft-v1` 0.2.0, 9 server cases)

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
| `target-negative-click-only` | target-negative, base starter + `target-negative-click-only.patch` | passed | 44/44 pass | yes |
| `compat-negative-escape-everything` | compat-negative, base starter + `compat-negative-escape-everything.patch` | passed | 44/44 pass | yes |
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
| `starter` | `run-d447afd2558b4662` | 40 | complete | expected failure |
| `reference` | `run-0deb3bd6fa304b91` | 100 | complete | all cases pass |
| `target-negative-click-only` | `run-9c6eca234578410a` | 40 | complete | expected failure |
| `compat-negative-escape-everything` | `run-6957be4c82b24dae` | 40 | complete | expected failure |
| `alternative-a` | `run-c8d22e79c18446a0` | 100 | complete | all cases pass |
| `reference-repeat-2` | `run-b077d70cd05e43f1` | 100 | complete | all cases pass |
| `reference-repeat-3` | `run-3bcad38f35994297` | 100 | complete | all cases pass |
| `tamper` | `run-e92e4b095b4b4ae2` | 100 | complete | all cases pass |

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
`gcb-scratch-betterteams-description-tag-injection` built from `tests/` (base
`gcb-minecraft-paper-verifier:1.21.11-132`, Apache Maven 3.9.11 installed and the
dependency cache warmed with `dependency:go-offline test`, then proved with
`-o clean test package`), run with `--network=none --cap-drop=ALL`, 2026-09-22.
Every run was complete (offline `mvn -o -pl BetterTeams -am package`, 44 upstream
JUnit cases, six server cases all observed); wall time 39–55 s per run.

| Control | Submission | Result | Failed cases |
| --- | --- | --- | --- |
| starter (`nop`) | `environment/plugin` unchanged | complete, not passed, 0 | `a click tag in a description is shown as text without a click event`, `a hover tag in a description is shown as text without a hover event` (both target; the tag text is consumed: `Description: CLICKME hello`, `Description: HOVERME done`) |
| reference (`oracle`) ×3 | starter + `solution/after` | complete, passed, 1 three times | none |
| alternative | starter + `InfoCommand.displayTeamInfo` sending `Formatter.legacy().process(str)` (the base's colour/decoration-only MiniMessage instance) as a component with the prefix | complete, passed, 1 | none |
| target-negative | starter + `InfoCommand.getInfoMessages` escaping only `<click` in the description (`replace("<click", "\\<click")`) | complete, not passed, 0 | `a hover tag in a description is shown as text without a hover event` only |
| compat-negative | starter + `InfoCommand.getInfoMessages` escaping every tag in the description (`MiniMessage.miniMessage().escapeTags(...)`) | complete, not passed, 0 | `a colour tag in a description still colours the text` only (server, preserved: `Description: <red>hello</red> <bold>team</bold> ok`) |
| tamper | reference plus `THIS IS NOT XML` appended to `BetterTeams/pom.xml`, `ExtUtilTest.java` deleted and a non-compiling line appended to `ExtensionInfoTest.java` | complete, passed, 1 (frozen paths restored, 44/44 unit cases, verdict unchanged) | none |

The alternative, negative and tamper diffs are kept next to the scratch pack
(`gates/*.diff`).
