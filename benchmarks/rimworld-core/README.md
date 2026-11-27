# RimWorld core benchmark pack

`rimworld/core` is the first reviewable RimWorld pack for Rhenium 0.6. Catalog
0.5.0 contains ten C# debugging tasks and a managed-runtime declaration for
RimWorld 1.6.4871. The original R⁴ material-basis task retains its 38-case private
protocol v2 contract; the other nine tasks use explicit protocol v3 manifests with
task-specific assertion counts. Catalog 0.5.0 retired the Zombieland task, which was
saturated and no longer discriminated; its files stay here as history. The pack is `In Development`. On 2026-09-24, after
verifier repairs, nine tasks completed two-way validation in the real game on one
Linux x86_64 Docker host: each reference scored 100 three times with identical case
outcomes and each unchanged starter completed and failed only its target cases.
Catalog 0.4.0's Research: Organized research-tab task passed the same validation
on that host on 2026-10-29, after two verifier fixture repairs. Adaptive Storage
now passes local reference compilation with the pinned SDK, but has no engine
result for the repaired inputs. E0 study controls live under
`private/study-controls/`.

The pack is immutable benchmark input. Listing, preparation and evaluation may
read it, but generated build contexts, game data, compiler output, saves and logs
belong in Rhenium state/cache directories. The pack and plugin contain no RimWorld
DLL, game binary, Steam state, Workshop cache, precompiled Mod assembly or excluded
R⁴ visual asset.

See [the RimWorld support notes](../../docs/games/rimworld.md) and each task's
`validation/provenance.md` for exact source, license, exclusion, and not-run
decisions.

Catalog 0.3.3 records [Adaptive Storage authoring revision 4](../../docs/games/rimworld-authoring-revision-4.md).
It preserves the prior [revision 3](../../docs/games/rimworld-authoring-revision-3.md)
for the other tasks. Adaptive Storage uses a fixed native 1.6 source graph, reviewed
sentinel semantics and 15 cases, with deterministic historical-behavior
reconstruction and mutation materialization. At catalog 0.3.3, its starter and
reference used C# 14 lambda syntax that the pinned .NET 8.0.422 compiler rejected. Catalog 0.3.4
[revision 5](../../docs/games/rimworld-authoring-revision-5.md) lowers those
three lambdas and aligns the rectangle adapter with `CellRect.Cells`. Fresh
base/reference/no-op candidates and verifiers compiled on macOS arm64 with
SDK 8.0.422; Linux container and all real-engine controls remain unrun. See the
[engine validation record](../../docs/games/rimworld.md#engine-validation-2026-09-24).
