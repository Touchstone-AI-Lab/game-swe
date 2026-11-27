# Adaptive Storage provenance — authoring revision 4

Current status: source-authored, not compile-validated or engine-validated; Draft only.
The authoritative current decision and migration record is
[revision 4](../../../../../../docs/games/rimworld-authoring-revision-4.md).
[Revision 2](../../../../../../docs/games/rimworld-authoring-revision-2.md) and
[revision 3](../../../../../../docs/games/rimworld-authoring-revision-3.md)
retain the historical partial-source and fixture findings; their 12-case counts,
exact historical-base claims and unresolved 14-file inventory are not current.

The fixed repository is https://github.com/bbradson/Adaptive-Storage-Framework.
Independent GitHub API reads establish historical target
`6c403b09e22508fa929673caaec2877aa56ac9b5` has sole parent
`2d0aef23f7b8592f9eedaaf8c8fc47b4dd1f0f5a`, and native 1.6 source
`31ee88b46651cfbe37da3f89620bc0b907165cc0` descends from target (21 ahead, zero behind).
The scored PostInitialize/setter fix remains unchanged. Both candidate baselines
use this same 1.6 graph and fixed build dependencies.

[Source derivation](source-derivation.json) contains all 170 input/base/oracle
hashes, archive and license hashes, 13 unique mechanical property adaptations in
six files, and the single historical-bad-behavior transformation in ThingClass.
Oracle ThingClass is exact upstream; the starter is a historical-behavior
reconstruction, not byte-exact historical source. [Reconstruct tool](reconstruct_source.py)
validates every hash/anchor before writing to fresh task state outside the pack.
Both trees preserve full production paths and pre-existing duplicate files.

[Dependencies](dependencies.json) and [closure audit](closure-audit.json) record
compile units, source notices, public packages, BCL/private access and unrun
validation. Main source is MIT, 30 Fishery units carry MPL-2.0, and MultiplayerAPI
has its own MIT notice. StorageCellRect's Verse-derived upstream body is excluded;
Support delegates its actual rectangle contract to the public game API. Its
runtime checks remain unrun, and no rights to the excluded body are asserted.
All copied source retains licensing/provenance. Benchmark Support, Harness,
projects, scripts and manifests are authored infrastructure, not upstream source.
No game/Workshop assets, licensed runtime DLL, precompiled candidate, save, secret,
NuGet archive or execution log is included in the pack.

The public spec preserves exact logical limits including the unlimited sentinel;
unchecked temporary overflow is permitted solely as a backing-value transition.
The real setter, per-cell capacities, notifications and complete initialization
are required. [Manifest](../tests/assertions.json) has 15 protocol-v3 cases and
10/90 scoring, with bracketing fixture integrity gates. Expected observations
remain external to generated candidate/adapter dispatch. Candidate mismatches are
complete failures only when fixture, runtime, identity and cleanup are healthy.

[Control plan](controls.json) and [14 mutations](mutation-controls.json) are
reviewed expectations, not engine outcomes. Independent materialization and
source/hash tests passed; all C# compilation and real engine runs are unrun due
to the absent existing toolchain and controlled host. No prior evidence is reusable.
The [compile runner](reference_compile.py) can run on an existing pinned SDK; it
never installs software, invokes Steam, prepares a runtime or launches the game.
Local execution logs and independent review belong exclusively to task state,
not to this immutable benchmark input.

## Engine validation (2026-09-24)

Blocked. The pinned .NET SDK 8.0.422 compiler rejects three C# 14 lambdas in
`Source/AdaptiveStorage/StorageRenderer.cs` (`static (data, phase, in transform) =>`
and two like it; CS1001), identically in the starter and the reference, so no
submission of this task can compile and no engine run is possible. The C# 12
lowering recorded in `source-derivation.json` covered field-backed properties but not
these lambdas. Fixing it means lowering the three lambdas in both trees or pinning a
newer SDK image; neither is a verifier repair, so both are left to the maintainers.
With the lambdas given explicit parameter types in a scratch copy, the reference and
harness compiled and the `runtime-defs-ready` gate failed its `StorageCellRect`
enumeration check, so the harness needs further work before a first engine result.
The harness gained `using System.Globalization` (the serializer's `CultureInfo`),
and the five adapter-mutation digests in `mutation-controls.json` follow that file.

## Build compatibility repair (2026-10-26, authoring revision 5)

Catalog 0.3.4 supersedes the blocked compilation record above. The unmodified
reference reproduced CS1001 at all three recorded locations with SDK 8.0.422.
Both starter and reference now give those lambda parameters explicit types,
preserving their bodies, context types and `in TransformData` passing. The three
unique transformations and new output hashes are recorded in source-derivation
and dependency inventories; upstream input hashes are unchanged. Source notices
record the additional adaptations. ThingClass and the historical regression
transition are unchanged.

The independently authored rectangle wrapper now enumerates `CellRect.Cells`,
the public enumerable path, rather than using the struct's pattern enumerator.
The existing verifier's empty-width, coordinate, area and containment checks
remain unchanged. This aligns the delegation paths; whether it resolves the
reported real-game gate failure remains unvalidated on the pinned game.

Fresh independent base, oracle and no-op candidates and their corresponding
verifiers passed locked restore and reference compilation on macOS arm64 with
SDK 8.0.422, net472 and C#12. Candidate builds each retain 560 upstream warnings
and zero errors; verifiers have zero warnings and errors. The curated assembly
hashes are in controls.json; full commands and logs remain in local task state.
No licensed game was acquired or launched, and no Linux container was rebuilt.
All 15 assertions, weights, public exam, production slot behavior, and mutation
expectations remain unchanged. No previous engine evidence applies to these
changed source/adapter inputs. See the revision 5 record for rerun commands and
the outstanding real-engine gate.
