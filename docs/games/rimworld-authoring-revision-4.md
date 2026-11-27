# RimWorld catalog 0.3.3 / Adaptive Storage authoring revision 4

Date: 2026-09-13. Status: **source-authored; reference compilation unavailable;
real-engine validation unrun; Draft only**. This revision changes only
`adaptive-storage-slot-limit-restore` and the catalog version. The ten-task count
is unchanged. R4 retains protocol v2, 38 assertions and 10/90; its manifest SHA-256
remains `ab0f4ca774ce0a626ac0e83849c2eec177f898b32170da0bb85d2320ca0c1be7`.
Revision 2 and revision 3 documents remain historical records.

## Contract decision and evidence invalidation

The old demand to change the backing value without any arithmetic overflow,
preserve an already-unlimited value, and never finish at `int.MaxValue` was
internally contradictory. The historical target uses `_currentSlotLimit++`:
with unchecked integer arithmetic, `int.MaxValue` temporarily wraps to `int.MinValue`;
with checked arithmetic it throws. Neither exception nor a changed saved logical
limit is the intended production behavior.

The revised contract preserves the exact saved logical backing value, including
`int.MaxValue` as the unlimited sentinel. Immediately before the real
`CurrentSlotLimit` setter runs, the backing value must differ from the saved value
so the setter cannot early-return. The setter must rebuild per-cell capacity and
perform the associated notifications; all required initialization must finish.
The final backing value may be `int.MaxValue` precisely for an unlimited input.
The public getter remains the upstream effective bound `min(backing, TotalSlots)`.
A temporary unchecked wrap is permitted, must not throw, and must not escape as
the final logical or per-cell state. Equivalent implementations are accepted;
no assertion requires the increment line. C# overflow checking is explicitly off.

The 15-case v3 manifest retains 10/90 weighting and bracketing integrity gates.
It preserves ordinary finite, zero, near-unlimited, unlimited, multi-cell and
repeated initialization cases. `NoOverflow` is replaced by the actual unlimited
sentinel behavior, the setter observer checks entry with a distinct backing value,
and notification/full initialization checks are added. This is a reviewed
specification correction, not a change to expected values based on an oracle run:
no oracle run exists. Catalog 0.3.2 evidence, old 12-case counts and planned 5/7
base splits are invalid for this revision. Adaptive Storage authoring revision is
4; other tasks retain their prior revisions. Core/plugin API/schema versions do
not change. No release or commit was made. A future commit for this semantic
migration must include a `BREAKING CHANGE:` footer identifying the catalog and
non-comparable old Adaptive Storage results; this document is its migration record.

## Fixed production baseline

The historical target
[`6c403b09e22508fa929673caaec2877aa56ac9b5`](https://github.com/bbradson/Adaptive-Storage-Framework/commit/6c403b09e22508fa929673caaec2877aa56ac9b5)
has sole parent `2d0aef23f7b8592f9eedaaf8c8fc47b4dd1f0f5a`.
The fixed native 1.6 descendant
[`31ee88b46651cfbe37da3f89620bc0b907165cc0`](https://github.com/bbradson/Adaptive-Storage-Framework/tree/31ee88b46651cfbe37da3f89620bc0b907165cc0)
is ahead of the target by 21 commits and behind by zero, as independently fetched
from the GitHub commit and compare APIs. Both `PostInitialize` and the setter
retain the target's relevant production code. Other descendant changes include
label/stuff settings moved into Extension, room highlighting, blueprint/frame
updates and spawned storage-group repair. Both candidate baselines use those same
changes; the task's definition-level slot contract does not intentionally score
them. Their runtime interaction remains part of the unrun engine validation.

The oracle contains 170 fixed production C# units. Six files mechanically lower
13 contextual `field` properties to explicit private compiler-generated fields
for C#12, preserving initialization order, attributes and accessor bodies.
`ThingClass.cs` in the oracle is byte-exact descendant source. The starter changes
only the unique three-line saved-limit transition's middle line from increment
to `_currentSlotLimit = int.MaxValue;`. It is a **historical-behavior reconstruction
on the 1.6 baseline**, not a byte-exact historical base. No production branch,
notification, renderer, UI/packing, compatibility or startup implementation was
deleted. Pre-existing `ThingClass 2.cs` duplicates remain untouched and are not
included in compilation.

The task's `validation/source-derivation.json` pins every input/output SHA-256,
all 13 unique adaptation anchors and the unique historical reconstruction anchor.
`reconstruct_source.py` validates all inputs and expected outputs before writing
only to a fresh destination outside the pack, rejecting ambiguous anchors,
incorrect hashes and unsafe destinations. Independent replay against freshly
fetched upstream bytes reproduced both current source trees.

| Input | SHA-256 |
| --- | --- |
| Fixed 1.6 source archive | `2cbb9532568d0114bab87b2e36317c7937694d919824f12fc600372ae0dea65c` |
| Oracle ThingClass | `7106bc1cbbddc4d7c3c4f55df92ad131520aa2b2411022475bc0c1326744467d` |
| Reconstructed base ThingClass | `dbea56f31b75e62a1f0a3e394f4c93e55adaa0923627ca5f5c365f1c2aafe953` |
| Historical base ThingClass, audit only | `1e1eb3e8eb704946add678965831ed4cdf9747e44e394f306be8f8d28f2a3240` |
| Historical target ThingClass, audit only | `a1bea778dce6b5e6bdedcdc315013950ac6576803dd15e70fca7b96fe1781740` |
| Upstream MIT license | `c2f35bfff8d6afe40c93119455bcb6eb3b15f77e71cb31952984157076ec42b2` |

## Dependencies, access and license boundary

The full fixed source inventory includes Fishery, ITransformable, collections,
rendering, quality/Extension, labels, UI, packing, settings, Harmony patches and
optional compatibility code. Its 170 units plus benchmark Support are explicit
Compile items. Main project source is MIT; 30 Fishery units carry MPL-2.0 headers,
which are preserved along with the full MPL notice. One of those units has a
recorded mechanical adaptation; the corresponding source remains available in
both trees. No blanket-MIT claim applies to this combined source graph.

The excluded 171st upstream file, StorageCellRect, describes itself as Verse-derived;
rights to redistribute that implementation are not asserted. The authored thin
adapter in Support delegates rectangle construction, area, containment and
iteration to **public `Verse.CellRect`**, converting IntVec2/IntVec3 coordinates.
It does not copy the game/upstream body or implement slot restoration. The runtime
gate compares coordinates, empty bounds, area and traversal with real CellRect;
that check is authored but unrun. No redistribution rights to the excluded body are claimed.

Both baselines use net472, C#12, V1_6, deterministic builds, unchecked overflow and
explicit unsafe support. The existing .NET SDK image remains 8.0.422 bookworm-slim
at `sha256:63ebabdcde24cc8134304a6f50719cf1e22bb4e9f7148ac4ef967c7680187356`.
There is no relabeling to net48. Krafs.Rimworld.Ref 1.6.4871 supplies its own BCL
reference surface; resolution against Microsoft.NETFramework.ReferenceAssemblies
1.0.3/net472 1.0.3 and compatibility with Unity Mono still require actual compilation
and engine tests. The verifier references its corresponding candidate assembly.

Fixed packages add PolySharp 1.15.0, Krafs.Publicizer 2.3.0 and
RimWorld.MultiplayerAPI 0.6.0 to existing Harmony 2.4.2 and reference packages.
Publicizer uses 58 explicit member/type entries from actual V1_6 call sites,
including game map/storage state, Fishery Array/List/String access and specific
internal types; six unused or old-version entries are omitted. No assembly-wide
PublicizeAll is used. Its default Unsafe/IgnoresAccessChecksTo strategy is retained,
not represented as proof of runtime private-member compatibility.

The Multiplayer API's MIT source commit is
`2840872473baf7654fa05fe7a461ad71dae78722`; its static initialization uses a dummy API
when the Multiplayer assembly is absent. The task does not add the Multiplayer
Mod, an account or a network requirement. The pinned API library is copied from
the builder's locked package into the immutable evaluator image, then into the
candidate mod directory at launch. Whole-mod graphics-def patches, DefOf and
settings/UI startup remain real; asset-free startup and optional-mod/DLC behavior
have not been validated. No licensed DLL or package archive is stored in the pack.

`closure-audit.json` distinguishes sourceGraphAuthored from actual source/API
closure: sourceClosed/compileValidated/engineValidated remain false. It records
package archive SHA-256 separately from NuGet signed contentHash. The three added
lock entries and the existing Harmony entry in both candidate/verifier locks were corrected using the signature-excluding
[NuGet algorithm](https://github.com/NuGet/NuGet.Client/blob/d3a633a04da7cd83900498334ec5e7650a52fa86/src/NuGet.Core/NuGet.Packaging/Signing/Archive/SignedPackageArchiveUtility.cs#L593),
independently recomputed by the reviewer and cross-checked against the existing
RimWorld.Ref contentHash. This is not evidence that locked restore ran. Restore
uses only the explicit NuGet v3 source, with fixed versions/content hashes. The
inspected compiler toolset 4.13.0 was rejected because its runtimeconfig requires
.NET 9; it was not adopted, restored or executed.

## Fixture completion and failure classification

Returning from PostInitialize is insufficient because production catches and logs
exceptions. Each invocation must emit its completion event and leave consistent
per-cell capacity/bookkeeping, a valid ThingCollection with the correct parent,
cell count and empty per-cell lists, free-slot bookkeeping, and a renderer with
its parent and draw/print collections. Repeated initialization must finish again.
The fixture observes the real setter and its slot/settings events. A separate
notification case checks that Notify_SettingsChanged reaches the collection
update and renderer dirty routes after subscriptions are installed. Method-entry
observation does not prove every branch inside those production methods.

A task-owned subclass supplies white DrawColor values for renderer input; it does
not replace initialization, storage behavior or the setter. Mutable object fields
and array contents are snapshotted before fixture setup, with independently
registered restoration; static Initialized handlers and Harmony observers have
separate ownership and cleanup. Constructor failures occur within the candidate-operation boundary
before object-restoration obligations are registered, so they do not fabricate a
fixture failure for an object that never existed. Required cleanup after an
actual mutation remains mandatory. Global Def/settings/game boundaries and both
Rand compressed state and push depth are restored and rechecked.

Candidate construction, setter, notification or initialization postcondition
failures yield ordinary failed cases when fixture cleanup and runtime are healthy:
complete=true, passed=false. Missing fixture APIs, invalid CellRect delegation,
observer setup, absent/failed restoration, residual state, unmatched Rand pushes,
build/runtime failures and evidence identity violations are incomplete. Cleanup
failure takes precedence over a candidate mismatch. Engine controls must prove
these classifications; Python integrity tests do not execute candidate C#.

## Controls and next executable step

`materialize_control.py` independently creates base, oracle, nop and 14 mutations
in fresh state directories with source/adapter hashes and separate materialization
IDs. Those IDs are not evaluation IDs. Mutation anchors and output hashes are
fixed, and each plan declares triggered case(s) and expected completeness. The
production controls cover early return, setter bypass, wrong unlimited restore,
cell-update loss, missing notification/subscription, constructor failure, and
aborts after cells or after the setter. Fixture controls remove restoration,
throw during restoration, leave state behind, add an unpaired Rand push and
break the rectangle adapter. These are executable source transformations,
not observed control results.

| Execution | Actual current result | Required engine outcome |
| --- | --- | --- |
| base + corresponding verifier | Compiler unavailable; engine unrun | Historical regression, complete=true, passed=false |
| oracle + corresponding verifier | Compiler unavailable; engine unrun | All 15 manifest cases pass |
| independent nop + verifier | Compiler unavailable; engine unrun | Historical regression, complete=true, passed=false |
| 9 production mutations | Hash/materialization checked; engine unrun | Declared production cases fail, complete=true |
| 5 fixture mutations | Hash/materialization checked; engine unrun | Declared integrity failure, incomplete |

The inspected host is macOS arm64 with no existing dotnet, Mono/C# compiler,
Docker/Podman or devenv. No already-prepared controlled Linux engine artifact was
provided. No host software was installed, Steam login/acquisition performed or
runtime prepare invoked. Source work and safe checks continued; no engine score
or assembly hash is fabricated. Read-only independent review found no unresolved
confirmed source defect after corrections; compilation and engine acceptance
remain external blockers.

On an existing authorized host with SDK 8.0.422, from the repository root:

```sh
PYTHONPATH=src:plugins/rimworld/src .venv/bin/python \
  benchmarks/rimworld-core/private/harbor/adaptive-storage-slot-limit-restore/validation/reference_compile.py \
  /absolute/new/task-state/reference-compile --dotnet /existing/path/to/dotnet
```

The runner restores with --locked-mode and builds fresh base/oracle/nop and their
matching verifiers, logging commands, exit codes, toolchain/source/assembly hashes
outside the pack. It refuses existing output or a mismatching SDK and returns 2
when unavailable. Compilation alone does not run or validate the game. For engine
controls, an operator must supply an already-licensed/preconfigured Linux x86_64
host and immutable builder/evaluator artifacts matching **these final inputs**;
fixture mutations need their own matching adapter artifacts and every run a new
evaluation identity. No runtime prepare or shared image update is authorized by
this next-step instruction. An old image that fails input identity verification
cannot be reused. If matching artifacts do not exist, a separate reviewed
artifact-construction authorization is required before engine evaluation.
