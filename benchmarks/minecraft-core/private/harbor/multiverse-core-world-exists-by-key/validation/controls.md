# Acceptance gates: multiverse-core-world-exists-by-key

## 0.2.0 (catalog `rhenium-minecraft-v1` 0.2.0, 10 server cases)

### Offline evidence, 2026-11-02

Lab (Linux x86_64, Docker), task development image = `eclipse-temurin:21-jdk` with the task's
dependency cache warmed from the starter exactly like the verifier image, `--network=none`.
Each tree was synced and its frozen paths restored by `verify.py` itself, built offline, and
its upstream tests run; the grader suite was then compiled against GcbHarness, `paper-api`
1.21.11-R0.1-20260511.115010-91 and the built jar. No Paper server was started.

| Control | Tree | Offline build | Upstream unit cases | Suite compiles |
| --- | --- | --- | --- | --- |
| `starter` | starter, unchanged `environment/plugin` | passed | 177/177 pass | yes |
| `reference` | starter + `solution/after` | passed | 177/177 pass | yes |
| `target-negative-no-import-key-lookup` | target-negative, base starter + `target-negative-no-import-key-lookup.patch` | passed | 177/177 pass | yes |
| `compat-negative-key-only` | compat-negative, base starter + `compat-negative-key-only.patch` | passed | 177/177 pass | yes |
| `alternative-a` | alternative, base starter + `alternative-a` | passed | 177/177 pass | yes |

### Real-server gates — 2026-11-04

All required controls below completed through the Hub `full` profile on the real
Paper 1.21.11 build 132 server on Lab (Linux x86_64, Docker with networking disabled).
The operator explicitly recorded EULA acceptance, and `official-download` prepared
and verified the pinned runtime. Every execution used the final task image by
immutable ID, matching the current `tests/` build context. Every frozen case was
observed as pass or fail; the runtime sentinel passed in every control.

| Control | Run | Score | Full profile | Control verdict |
| --- | --- | --- | --- | --- |
| `starter` | `run-584f2f9a5ce64c24` | 40 | complete | expected failure |
| `reference` | `run-c720a468de9742c9` | 100 | complete | all cases pass |
| `target-negative-no-import-key-lookup` | `run-0c0ea864d8684098` | 40 | complete | expected failure |
| `compat-negative-key-only` | `run-59dbc08a54a6475e` | 40 | complete | expected failure |
| `alternative-a` | `run-fadd3fc15f9146ac` | 100 | complete | all cases pass |
| `reference-repeat-2` | `run-5b4d5c12c4fa4d44` | 100 | complete | all cases pass |
| `reference-repeat-3` | `run-9d70339f7af449ed` | 100 | complete | all cases pass |
| `tamper` | `run-552506a9ba1a480c` | 100 | complete | all cases pass |

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

The initial reference runs (`run-22ae60e0c4754bdf`,
`run-cdf9ae0ad4964f56`, `run-8af49910d8624759`) exposed a baseline error: the
unloaded-import assertion compared against the count before unloading. This
snapshot removes the loaded list entry during unload independently of import.
The case now measures immediately before import and also requires the rejected
import to retain the unloaded world under both its key and its name. Failure
reasons, case identities, exam, starter, reference and scoring are unchanged.
The initial failed records were retained rather than relabeled.

<!-- 0.1.0 record below -->

## 0.1.0 record (historical, superseded by 0.2.0)

Real Paper 1.21.11 build 132 server (`gcb-minecraft-paper-verifier:1.21.11-132`
base image), task verifier image built from `tests/` and run with
`--network=none --cap-drop=ALL --cpus=4 --memory=8g` through `tests/test.sh`,
2026-09-22. Every run was complete (offline `shadowJar` build, 177 upstream
MockBukkit cases and seven server cases all observed); wall time 79–99 s per
run. Reward is the verifier's 0/1 (`/logs/verifier/result.json`).

| Control | Submission | Result | Failed cases |
| --- | --- | --- | --- |
| starter (`nop`) | `environment/plugin` unchanged | complete, not passed, 0 | `create is rejected when the name is an existing world key` (`WORLD_CREATOR_FAILED`, Paper `IllegalArgumentException: Cannot create a world with key minecraft:the_end and name the_end ...`), `create is rejected when the key belongs to an existing world` (`IllegalStateException: WorldConfig for world gcb:keyed already exists`), `clone is rejected when the target key belongs to an existing world` (same exception for `gcb:clone_target`), `import adopts a loaded Bukkit world addressed by key` (`WORLD_FOLDER_INVALID`) — the four target cases only |
| reference (`oracle`) ×3 | starter + `solution/after` | complete, passed, 1 three times | none |
| alternative | starter + a `WorldManager`-only fix: private `hasLoadedWorld`/`hasWorld(WorldKeyOrName)` helpers that try the usable name and then the usable key string at the six existence checks, and a `findLoadedBukkitWorld` helper (`Bukkit.getWorld(name)` then `Bukkit.getWorld(NamespacedKey)`) in `importWorld`; no `WorldStore` or `BukkitCompatibility` change | complete, passed, 1 | none |
| target-negative | the alternative without the `importWorld` lookup change (existence checks fixed, import still `Bukkit.getWorld(usableName())`) | complete, not passed, 0 | `import adopts a loaded Bukkit world addressed by key` only |
| compat-negative | the alternative with key-only existence helpers (`isLoadedWorld(usableKey().toString())`, name lookup dropped) | complete, not passed, 0 | `creating or cloning under an existing name is rejected` (server, preserved: `createWorld(worldName("named"))` for the `gcb:named` world returned `WORLD_EXIST_FOLDER` instead of `WORLD_EXIST_LOADED`); all 177 unit cases still passed |
| tamper | reference plus `throw new GradleException(...)` appended to `build.gradle` and `WorldManagerTest.kt` deleted | complete, passed, 1 (verifier log: `frozen paths restored from the starter: build.gradle, settings.gradle, gradle, gradlew, gradlew.bat, src/test`; verdict unchanged) | none |

The alternative and negative diffs are kept with the authoring scratch
material (`gates/variants/*.patch`), not in the pack.
