# Zombieland source and validation provenance

## Exact public source audit

- Repository: `https://github.com/pardeike/Zombieland`
- Starter/base commit: `6cbe9b443fdf72969f61b3f03adaaca13b15fa46`
- Target commit: `f50cac11d97df1f8fc7f4aeada7e4c0842503c1b`
- Relationship: target is a single-parent successor whose sole parent is base
- Applicable license: MIT; copied byte-for-byte as `environment/Zombieland/LICENSE`
- Runtime dependency boundary: RimWorld Core plus Harmony only

GitHub's public commit object records the target's sole parent as the base. The 1.6 About metadata is present at target; no upstream bridge or test file is copied.

The revision-2 starter and oracle are **source slices, not byte-exact complete
upstream files**. `source-derivation.json` pins both complete upstream hashes,
three exact class blocks, the wrapper text and output hashes. `slice_source.py`
reproduces each output from a local verified upstream file and refuses edited
input or output inside the benchmark pack. No method body in the selected need,
capacity or no-pain patch classes is changed by the transformation.

The entire original Patches static initializer is excluded. It scheduled Twinkie
asset setup, PatchGroups discovery, CETools and optional Mod integrations, and
CrossPromotion installation. Those dependencies are not imported or invoked by
the source slice. No static initializer remains on the outer Patches class.

`tests/Support.cs` contains a Rhenium-authored `ZombieSymbiant : Pawn` boundary.
Its two HashSets supply the result of the unrelated linked-host mood/food/rest
service. They do not calculate need values, capacity floors, pain, or infected
membership. The fixture covers both selected and unselected inputs to the
unchanged production decisions. This does **not** validate symbiosis linkage,
map membership or biological behavior of the complete upstream Mod. The original
service source was read only in an isolated directory; it is not redistributed.
The scored patch scope and public production requirements remain unchanged.

Static source dependency inventory: System.Collections.Generic, HarmonyLib,
RimWorld, UnityEngine, Verse and the authored ZombieSymbiant boundary. The only
package references remain the pinned game reference, Harmony and net472
reference assemblies. Runtime namespace is `ZombieLand`; assembly is
`Zombieland`. Nested nonpublic patch classes are observed via reflection. No
Publicizer, other Mod, DLC, asset loader or network client has been added.
Reference compilation and real-game behavior remain **not-run**.

Source snapshot SHA-256 (full upstream → derived slice):

- base: `8db0a6746d56d40829d88630676dbf6653c57dac46b37b5cb5aa9135a25c52ff` → `cc09e90121bb8f8d224c55bdf6a3e38afeb9890981d3da4b947184fa64e40c4d`
- target: `a085f293276f67a4395abfa8e2ee8035b5424a98de2d47a7f0184babbd6c1cf8` → `f70510b3c49ef0ba714d5250a55c396b0939774751c14aa96e8076040aed83ec`
- MIT license: `a5883d0c45eb7e176d3d1631220e7f96e958e37064773d40245ae6db560bbd6d`

No upstream tests, bridge, save, fixture, binary, PDB, texture, sound, preview,
Workshop payload, runtime evidence, Steam data, or other asset was copied. The
benchmark-authored project, Support, verifier, Mod metadata, scripts, manifest,
and control plan are not represented as upstream files.

## Scored contract and private protocol

The scored production surface is `Need_CurLevel_Patch and PawnCapacitiesHandler_GetLevel_Patch`. `tests/assertions.json` is the
only maintained declaration of all 19 case IDs, fixtures,
expected observations, gate flags, and the 10/90 weighting. Protocol v3 exists
explicitly for variable per-task assertion counts; it does not reuse the legacy
R4 protocol-v2 identity. Runtime preparation generates only dispatch metadata.
Expected values and the manifest are not copied into a candidate-readable image,
workspace, or evaluation mount. Every fixture must restore Rand, Def, Settings,
Map, and object state it mutates; a gate failure makes evidence incomplete, while
a completed production mismatch is complete and failed.

## Validation status

Status: **source-authored, pending independent compile and engine validation**.

- reference compile: `not-run`
- builder/evaluator container construction: `not-run`
- real RimWorld launch: `not-run`
- oracle control: `not-run`
- independently materialized base control: `not-run`
- independently materialized no-op control: `not-run`

The planned oracle/base/no-op counts in `controls.json` are authoring expectations,
not execution evidence. No old control evidence exists or is reusable for this
task. Compile, container, and licensed engine work are assigned to a later,
independent validation owner.

## Authoring revision 2 fixture contract

Membership and external benefit-input sets have independent entry snapshots and exact set-equality restoration. A witnessed membership mutation precedes the cases. A minimal Pawn_HealthTracker supplies living/dead state without PawnGenerator or world kills. Both the base prefix and target postfix entry shapes are handled; no missing Postfix is mistaken for a fixture failure. Mood/food/rest/no-pain controls were added.

The v3 gates bracket behavior cases; the final gate retains and rechecks actual
restoration observations. BeginCase also checks independent boundary snapshots.
Cleanup failures poison the run instead of erasing evidence when callbacks are
cleared. Rand.StateCompressed is compared around PushState/PopState; a missing
observation API is a fixture failure. Each behavior case owns a temporary Game
so generated IDs/state cannot alter a pre-existing game. Publicizer/API details
of these new C# fixtures still require reference compilation. No source-text or
Python check is represented as a C# behavior result.

See [revision and migration review](../../../../../../docs/games/rimworld-authoring-revision-2.md)
for catalog/version/evidence invalidation and the required negative controls.

## Authoring revision 3

Production source/oracle bytes, manifest observations and counts are unchanged.
Fixture candidate-failure classification and source inspection are recorded in
the [revision 3 review](../../../../../../docs/games/rimworld-authoring-revision-3.md).
This supersedes revision 2 fixture claims where noted, without converting any
source inspection, Python protocol test or control materialization into C# or
engine evidence. All reference compile and engine controls remain not-run.

## Engine validation (2026-09-24)

This section supersedes the not-run statements above. Run through the Hub on one Linux x86_64 Docker host with the pinned RimWorld
1.6.4871 depot, networkless, after the verifier repairs recorded in
[the RimWorld support notes](../../../../../../docs/games/rimworld.md#engine-validation-2026-09-24).

- Reference (`solution/after` over the starter), `rhenium run` three times: `run-af954a4216224655` (100, 19/19), `run-ecbfa55fc6e34445` (100, 19/19), `run-a7954f5d90494544` (100, 19/19); identical case outcomes.
- Unchanged starter, `rhenium run` `run-1a6a6b0e04394aad`: complete, score 10, 13 passed and 6 failed (`food-benefit-preserved`, `infected-capacity-above-one`, `need-max-change-observed`, `need-max-fractional`, `rest-benefit-preserved`, `symbiant-capacity-above-one`).
- Independently materialized starter (study control) `run-7e2800c9188f4d99`: complete, 6 failed.
- E0 study controls and their outcomes: `private/study-controls/zombieland-dynamic-needs-capacities/NOTES.md`.
