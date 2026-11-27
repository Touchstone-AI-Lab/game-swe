# Enum identity r3 authoring review

On 2026-11-02 the maintainer explicitly authorized replacing the enum task's
execution vehicle, following the socket r3 precedent ("authorize the r3 rework").
Catalog 1.5.0 retires r2 (SG-134) and admits r3 (SG-161). The public exam stays
unchanged and the fifteen asserted behaviors stay unchanged; they now run after
ModTheSpire has launched the game. This is a new baseline, not a checksum update
that accepts an unexplained result. The r2 source, gold repair, author repairs,
manifest and all historical control records are preserved unchanged.

## Why r2 could not be scored

r2's verifier compiled each fixture mod and ran it in a fresh JVM through
`Loader.runMods` with `OUT_JAR` set. ModTheSpire patched and busted the enums,
exported a patched JAR and returned before `DesktopLauncher.main`; the fixture
then ran through ModTheSpire's class loader. The game never started. That does
not meet the real-game requirement in AGENTS.md, so plugin 0.7.0 kept the task
loader-only and its result was always incomplete.

## Scope and provenance

The public exam, `instruction.md`, starter tree, reference solution, build
template, `cases.json` (all fifteen expected observations) and the fifteen
fixture mods (`Fixture.java` and `ModTheSpire.json`) are byte-identical to r2.
The original ModTheSpire MIT provenance and licence accompany the copied tree.
Exactly these task files change:

- `tests/Runner.java` (removed): the standalone loader runner;
- `tests/observer/Observer.java` and `tests/observer/ModTheSpire.json` (added):
  the in-game observer mod that replaces it;
- `tests/run_probe.py`: launches the game once per case instead of the runner;
- `tests/score.py`: also requires in-game engine evidence for every case;
- `tests/test.sh`: calls the new driver with the same build, nonce and scoring
  steps, and adds the llvmpipe thread bound, log-permission check, host-name
  entry and ShellCheck annotation that the other native verifiers use;
- `task.toml`: the verifier limit grows from 1200 to 2700 seconds;
- `environment/Dockerfile`: the agent image bounds Maven's heap.

`tests/test_slay_the_spire_enum_revision.py` compares every r3 file with the
frozen r2 manifest and permits only these reviewed differences. The r3 manifest
binds the new bytes separately; r2 results are not inherited or relabeled. The
runtime version/fingerprint changes so that the new task set requires explicit
preparation through the pinned Steam provider.

## Execution vehicle

For each case the driver creates a fresh game directory: the submitted
ModTheSpire build, a link to the pinned `desktop-1.0.jar`, and a `mods/`
directory holding only that case's unchanged fixture mod and the observer mod.
It then runs, as the unprivileged `nobody` user under Xvfb with software OpenGL
and no network:

```text
java -jar ModTheSpire.jar --imgui --skip-launcher --skip-intro --mods enumscout,enumobserver
```

These are the launch options the six other native verifiers use. The submitted
ModTheSpire patches the game, busts the fixture's enums, initializes the mods
and starts `DesktopLauncher`. The observer's postfix on `CardCrawlGame.render`
waits until GL is live and the main menu has existed for three rendered frames.
It records whether the application listener is the `CardCrawlGame` whose render
it patched. On the game's render thread it then loads `enumfixture.Fixture`
through `Loader.getClassPool().getClassLoader()`,
the class loader r2 used, and invokes its unchanged `run()`. It records the same
`loaded`, `value` and `error` triple as r2, plus one nonce-bound engine record,
and exits the game. Each case has its own process, home directory, temporary
directory and mod list, so cases stay as isolated as r2's fresh JVMs.

The fixtures and the observer are compiled against the original public SDK
`ModTheSpire.jar`, as r2's were, so breaking existing compiled mods remains a
real contract failure. The observer has no switch statement, anonymous class or
enum, so it adds no switch-map holder or extension declaration that the
submitted loader could act on. It writes only its observation file.

## Scoring and fidelity

The fifteen expected `(loaded, value, error)` triples are unchanged. A case
passes only if its triple matches exactly. The result is complete only when the
build and fixture compilation succeed, every launch exits zero without timeout,
the cases appear in the r2 order, and each case has exactly one nonce-bound
observation and one engine record proving GL, the launched `CardCrawlGame` and
the main menu. Anything else is incomplete and cannot pass.

All fifteen behaviors could be observed faithfully inside the launched game.
The NOP starter fails exactly r2's ten intended cases with r2's raw outcomes
(for example `switch-delete` returns `33:11:22`, and `switch-add` and
`late-switch` raise `InvocationTargetException`). Two semantic boundaries are
disclosed:

- `loaded=true` now means the observer runs inside the launched game with the
  fixture mod loaded. In r2 it meant the patched JAR was exported.
- If the submitted loader cannot launch the game, no in-game observation exists
  and the result is incomplete, as for the other native tasks. r2 could instead
  report `loaded=false` for a loader exception that `runMods` caught. Every case
  requires `loaded=true`, so no passing outcome changes. The driver stops after
  the first failed launch because the result is already incomplete.

The game's own enum state is live when `game-color` runs: the game has used
`CardColor` throughout start-up. The fixture still counts six built-in colors
first, and gold still observes seven values, constants and set members.

## Agent image

Automatic preparation builds every admitted task's agent image under a
1536 MB build-container limit. On Lab's 104-CPU host, r2's unchanged recipe
(`mvn -B -o clean test package` with no heap bound) was killed at that limit,
which fails the whole preparation. r3 runs the same Maven goals with
`MAVEN_OPTS=-Xmx512m`, the bound the SDK build already uses. The starter bytes
and goals are unchanged. Preparation rewrites the historical agent image ID in
`task.toml`, as for every native task.

## Validation policy

Require, through the Hub with the `full` profile on the automatically
Steam-prepared catalog 1.5.0 runtime: a complete NOP result with exactly r2's
ten failed case IDs; two complete 15/15 gold results; the independent r2
alternative at 15/15; and r2's three isolated repairs with their original failed
case sets. Also replay NOP and gold of the six other admitted tasks against the
same runtime. Retain raw logs privately; commit only compact receipts and
hashes, never licensed images, trajectories or model submissions.

## Results

On 2026-11-02, `rhenium runtime prepare` built the catalog 1.5.0 runtime on Lab's host
Docker 29.8.1 (containerd image store) from the pinned Steam depot, including the enum
agent image. Every enum control then ran through the Hub with the `full` profile and
matched its prediction with a complete observation set:

| Control | Result | Failed cases |
| --- | --- | --- |
| NOP starter | 5/15 | r2's ten: `alias-existing`, `alias-new`, `game-color`, `late-switch`, `switch-add`, `switch-delete`, `warm-add`, `warm-delete`, `warm-replace`, `warm-undo` |
| Gold | 15/15, twice | none |
| r2 alternative | 15/15 | none |
| Alias repair only | 7/15 | r2's eight |
| Cache repair only | 10/15 | r2's five |
| Switch repair only | 8/15 | r2's seven |

The same runtime replayed NOP and gold of the six other admitted tasks; every gold run
passed and every NOP failed exactly its recorded case set. Run IDs, receipt hashes and
runtime identity are in `author-controls.json` and
`../lab-steam-runtime-controls-catalog-1.5.0.json`. Before the Hub runs, direct
prototype runs of the frozen verifier in the base image gave the same six outcomes; the
whole NOP and gold verifiers took 219 and 382 seconds, including the Maven build. The Hub
runs took 185 to 427 seconds while other controls ran beside them. Raw logs remain
private.
