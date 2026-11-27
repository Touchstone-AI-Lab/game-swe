# Slay the Spire benchmark pack

Catalog **1.8.0** registers nine Java source-repair tasks. Plugin **0.7.0** admits
all nine; each launches the real licensed game under ModTheSpire. The retired
loader-only tasks' historical results are not full game-backed benchmark results.

| Admitted real-game task | Required cases |
|---|---:|
| `basemod-dynamic-descriptions-r2` | 46 |
| `stslib-block-ledger-r1` | 27 |
| `stslib-icon-layout-r1` | 43 |
| `downfall-stasis-lifecycle-r1` | 38 |
| `basemod-phase-transitions-r1` | 32 |
| `downfall-socket-flow-r3` | 13 |
| `mts-enum-identity-r3` | 15 |
| `mts-load-order-regressions-r2` | 9 |
| `mts-mod-identity-regressions-r2` | 7 |

## Preparation and evaluation

Use the Steam provider with an account that owns Slay the Spire:

```sh
rhenium auth login steam
rhenium runtime prepare slay-the-spire/sts-native-646570-build10180494
rhenium runtime verify slay-the-spire/sts-native-646570-build10180494
```

Preparation downloads app 646570, depot 646571, manifest 9072802409324604124
(build 10180494), checks `desktop-1.0.jar` against its pinned SHA-256, and builds
local evaluator images from pinned public SDK sources. No login, acquisition,
update or runtime rebuild occurs during evaluation. Reprepare after upgrading
to catalog 1.7.0 because the runtime version/fingerprint binds the new task set.
The recipe constructs only the nine admitted source images. The retired tasks are
preserved as historical source and evidence but are not prepared by the Hub.

The [runtime guide](private/native-runtime/README.md) describes the required
Linux x86_64 Docker environment, public dependency cache, recipe hashes and
historical reconstruction commands. A manually supplied game JAR or
manual Harbor installation does not satisfy automatic benchmark acquisition.
Preparation uses network for pinned inputs; SDK builds and game verification
run without network. Missing engines, failed builds, malformed observations and
unsuccessful verifier exits fail closed. `core` is always incomplete.

The public tools image at `ghcr.io/changyiyang/swe-game-sts-tools` is pinned by
registry digest and contains no game, compiled SDK, task, solution or credential.
Game-bearing images and all generated state remain local and non-redistributable.
The verifier compiles submitted sources separately and uses Xvfb/software OpenGL
and real game APIs. Nonce-bound unique observations, exact case counts and
completion are required for a passing full result. This is an honest-mode
boundary, not a cryptographic sandbox against hostile Java.

## Socket baseline revision

The explicitly authorized r3 revision replaces r2 (SG-138, retired) with r3
(SG-159). The public exam, starter, solution, build template and original visible
behavioral expectations are unchanged. The probe fixes fixture initialization,
software-renderer frame drops and phase deadlines. Scoring additionally requires
the intended action phase, so an ineffective click cannot pass a cancellation
control. The shell entry point changes only an indirect-trap lint annotation.
Every other task file is checked against the frozen r2 manifest; Git attributes
preserve the upstream bytes on clean checkouts.

The [revision review](validation/native-engine/downfall-socket-flow-r3/revision.md)
describes the instrumentation and new control policy. The
[final Lab controls](validation/native-engine/lab-steam-runtime-controls-r3.json)
completed all six real-game NOP/gold pairs with 199/199 gold assertions and the
exact intended NOP failures; all three socket repair variants matched their
expected outcomes. r2's source, historical
3/13 Lab gold failure and reference remain preserved. r3 inherits no result
from r2.

## Enum baseline revision

The explicitly authorized r3 revision replaces the enum JVM probe r2 (SG-134,
retired) with r3 (SG-161). The public exam, starter, solution, build template,
fifteen fixture mods and their expected observations are unchanged. r2 ran each
fixture through a standalone loader that exported a patched JAR and never started
the game. r3 starts the licensed game through the submitted ModTheSpire once per
case, with only that case's fixture mod and an observer mod. The observer runs
the unchanged fixture on the game's render thread once the main menu is live.
Scoring additionally requires nonce-bound evidence of that launched game for
every case. The agent image bounds Maven's heap so automatic preparation can
build it. Every other task file is checked against the frozen r2 manifest.

The [revision review](validation/native-engine/mts-enum-identity-r3/revision.md)
describes the execution vehicle and control policy. The
[Lab controls](validation/native-engine/mts-enum-identity-r3/author-controls.json)
record complete real-game NOP, gold, alternative and isolated-repair results
through the Hub. r2's source, reference and author repairs remain preserved. r3
inherits no result from r2.

## Standalone task revisions

The user authorized reworking the three standalone ModTheSpire tasks the same way as
enum r3. Catalog 1.6.0 retires `mts-load-order-regressions` (SG-129) in favor of
`mts-load-order-regressions-r2` (SG-162). Its exam, starter, reference and private JUnit
suite are byte-identical to r1. The verifier builds the submitted sources with the
upstream build template and the licensed game, launches the game with that build, and
runs the unchanged suite inside it through the JUnit Platform launcher. It always leaves
out the starter's two loader-only stand-ins for game classes, which would shadow the real
game. The [revision review](validation/native-engine/mts-load-order-regressions-r2/revision.md)
and [Lab controls](validation/native-engine/mts-load-order-regressions-r2/author-controls.json)
record the Hub results: NOP 5/9 with r1's four target failures, gold 9/9 twice, the
study-control alternative 9/9 and both negative controls with their recorded failures.

Catalog 1.7.0 does the same for `mts-mod-identity-regressions` (SG-130), now
`mts-mod-identity-regressions-r2` (SG-163). Its
[revision review](validation/native-engine/mts-mod-identity-regressions-r2/revision.md)
and [Lab controls](validation/native-engine/mts-mod-identity-regressions-r2/author-controls.json)
record NOP 3/7 with r1's four target failures, gold 7/7 twice, the study-control
alternative 7/7 and both negative controls with their recorded failures. The
[catalog 1.7.0 replay](validation/native-engine/lab-steam-runtime-controls-catalog-1.7.0.json)
repeats NOP and gold of all nine admitted tasks on the final runtime.

Catalog 1.8.0 retires `mts-loader-internals-regressions` (SG-131) without a replacement.
Its starter's injected `PostfixPatchInfo` defect makes the loader treat a void method's first
postfix parameter as a result. ModTheSpire's own core postfix `ModsScreenUpdateRender$Render`,
on the void `MainMenuScreen.render`, then fails to compile, patching aborts and the real game
never launches for an unrepaired submission. No assertion can be observed in the game for
the NOP, so the required NOP gate is impossible there; the reference passed 16/16 in a Lab
prototype of the in-game harness. Its exam, source, verifier and study controls are
preserved unchanged.

## Historical records

Author matrices, independent alternate repairs and caveats for the native tasks
are in [native validation](validation/native-engine/README.md). The
[original pack report](validation/original-modthespire-pack.md) preserves the
standalone tasks' original caveats. Historical 214-case receipts include the enum
JVM probe and socket r2; they are not current r3 evidence.

## Source and layout

`catalog.json` contains bilingual public metadata; `exams/` holds public reports.
`private/harbor/` holds source snapshots, private verifiers and reference repairs.
`validation/` records provenance, author controls and historical control receipts.
Generated attempts, logs, caches and licensed artifacts belong outside the pack.

Materialize the 24 StSLib image pointers with Git LFS before preparing runtimes.
The frozen manifests bind their actual image contents and reject pointer text.
Upstream licenses accompany every snapshot and
[runtime dependency](validation/native-engine/licenses/). The repository contains
no licensed game, compiled native SDK, prepared game image, credential or model
trajectory. Original ModTheSpire snapshots retain their upstream Maven wrappers.
Related source families must stay together across dataset splits; separate task
IDs do not imply statistical independence. See
[independence.md](validation/native-engine/independence.md).
