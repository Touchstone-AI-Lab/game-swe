# Load-order r2 authoring review

On 2026-11-02 the maintainer explicitly authorized reworking the three standalone
ModTheSpire tasks the same way as enum r3 ("rework them as real-game tasks too"). The exam and
the private assertions stay unchanged; they now run after ModTheSpire has launched the
game. `mts-load-order-regressions` (SG-129) is retired and `mts-load-order-regressions-r2`
(SG-162) replaces it. The r1 source, reference, verifier and study controls are
preserved unchanged.

## Why r1 could not be scored

r1 staged its private JUnit suite into the submitted tree and ran `mvn -B -o clean test`
in a Maven container without the game. Its starter carries a stripped `pom.xml` (no
game dependency, `patches/**` not compiled) and two stand-ins for game classes so that
loader-only build compiles. It never started the game, which does not meet the real-game
requirement in AGENTS.md, so plugin 0.7.0 kept it loader-only and always incomplete.

## Scope and provenance

The public exam, `instruction.md`, the reference solution and every private suite source
(`Target.java`, `TargetPatch.java`, `ByRefBoxingTest.java`, `LoadOrderTest.java`) are
byte-identical to r1. The starter tree is byte-identical too; it moves from
`environment/modthespire/` to `environment/project/`, the layout every native task uses,
so the Hub workspace holds it as `project/`. The upstream ModTheSpire MIT licence travels
with it. These files are new:

- `environment/Dockerfile`: the agent image now builds from the native runtime base and
  keeps r1's offline Maven contract (`clean test` with a throwaway JUnit test, then the
  tree is restored);
- `task.toml`: the native task format, with the submitted `src/main/java` as artifact;
- `tests/test.sh`, `tests/score.py`, `tests/expectations.json`: the real-game verifier;
- `tests/observer/Observer.java`, `tests/observer/ModTheSpire.json`: the in-game runner;
- `tests/build-template.tar.gz`: the upstream ModTheSpire 3.30.3 build template already
  used by the enum task (`pom.xml` with the game dependency, and resources).

`tests/test_slay_the_spire_standalone_revisions.py` checks every r2 file against r1 and
permits only these reviewed differences.

## Execution vehicle

The verifier copies the submitted `src/main/java` into the upstream build template and
builds it offline with the licensed game on the class path, so ModTheSpire's core patches
compile as upstream builds them. It leaves out exactly two starter files,
`com/megacrit/cardcrawl/core/CardCrawlGame.java` and
`com/megacrit/cardcrawl/desktop/DesktopLauncher.java`. They are r1's loader-only stand-ins
for game classes. In a launch they would shadow the licensed game: ModTheSpire's class
loader asks its parent first for every game class except `DesktopLauncher`, so a stub
`CardCrawlGame` inside `ModTheSpire.jar` would replace the game's own. These two paths are
always excluded, whatever a submission writes into them; editing them has no effect on the
result. Every other submitted source file is built. As in the other native tasks, only the
submitted `src/main/java` is read, so edits to the starter's `pom.xml` are not used.

The unchanged suite is compiled against the submitted build, as Surefire compiled it
against `target/classes`. The game then starts as `nobody` under Xvfb with software OpenGL
and no network, through the submitted loader:

```text
java -cp ModTheSpire.jar:lib/suite.jar:<JUnit> com.evacipated.cardcrawl.modthespire.Loader --imgui --skip-launcher --skip-intro --mods suiteobserver
```

The suite and JUnit 5.10.2 sit on the game's system class path, as Surefire put them on
the test JVM's. The observer mod's postfix on `CardCrawlGame.render` waits until GL is
live and the main menu has existed for three rendered frames. On the render thread it runs
the JUnit Platform 1.10.2 launcher over the classes Surefire's default includes select
(`ByRefBoxingTest`, `LoadOrderTest`), with the system class loader as context loader,
Surefire's default. It records each test's terminal status and one engine record under the
run nonce, then exits the game.

## Scoring and fidelity

The nine expected case IDs (`gcb.<class>.<method>`) are exactly r1's nine assertions; r1
declared `EXPECTED=9`. A case passes only if JUnit reports it `SUCCESSFUL`. The result is
complete only when the build, suite compilation and game exit succeed, the engine record
proves GL, the launched `CardCrawlGame` and the main menu, every expected case is observed
exactly once, and none is skipped or aborted (r1 required `Skipped: 0`). A failed
container, a launcher error or any unexpected record is incomplete.

All nine assertions could be observed faithfully inside the launched game. The NOP starter
fails exactly r1's four target cases (`byRefWritesBackThroughAWrapperArray`,
`aChainOfDependenciesResolves`, `aDependencyIsInitialisedBeforeItsDependent`,
`anEdgeIntoTheNewestModTakesEffect`), and the reference passes all nine. A submission whose
loader cannot launch the game produces no in-game observation and is incomplete, as for
the other native tasks; r1 would have reported its Maven failures instead.

## Native recipe

The suite and the agent image need JUnit 5.10.2, JUnit Platform 1.10.2 and 1.9.3,
opentest4j, apiguardian and the Surefire 3.2.5 JUnit Platform provider. They are added to
the locked public Maven cache, each pinned by path, size and SHA-256 and checked against
Maven Central at authoring time; preparation verifies them again before use. The values
match the artifacts r1's agent image had warmed.

## Validation policy

Require, through the Hub with the `full` profile on the automatically Steam-prepared
runtime: a complete NOP result with exactly r1's four failed cases; two complete 9/9 gold
results; the independent study-control alternative at 9/9; the target-negative control
(reference without the by-reference boxing fix) failing only
`byRefWritesBackThroughAWrapperArray`; and the compat-negative control (reversed initial
sort order) failing exactly `control_everyModSurvivesWithNoDependencies`,
`mutuallyDependentModsKeepTheirOrder` and `aCircularDeclarationDoesNotRunAway`.

## Results

On 2026-11-02, `rhenium runtime prepare` built the catalog 1.6.0 runtime on Lab's host
Docker 29.8.1 (containerd image store) from the pinned Steam depot. Preparation fetched
the pinned JUnit artifacts and built the r2 agent image, whose offline `clean test` check
passed. Every control then ran through the Hub with the `full` profile and matched its
prediction with a complete observation set:

| Control | Result | Failed cases |
| --- | --- | --- |
| NOP starter | 5/9 | r1's four targets |
| Gold | 9/9, twice | none |
| Study-control alternative | 9/9 | none |
| Target-negative (by-reference boxing fix left out) | 8/9 | `byRefWritesBackThroughAWrapperArray` |
| Compat-negative (reversed initial sort order) | 6/9 | `aCircularDeclarationDoesNotRunAway`, `control_everyModSurvivesWithNoDependencies`, `mutuallyDependentModsKeepTheirOrder` |

Each outcome equals r1's recorded E0 result for the same control. Run IDs, receipt hashes
and runtime identity are in `author-controls.json`. Before the Hub runs, direct prototype
runs of the frozen verifier gave the same six outcomes with JUnit mounted into the base
image; whole verifier runs took 46 to 326 seconds while other controls shared the host.
Raw logs remain private.
