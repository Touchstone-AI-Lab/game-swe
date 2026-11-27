# Rimsential - Total Control: Continued source and validation provenance

## Exact public source audit

- Repository: `https://github.com/feldoh/TotalControl`
- Starter/base commit: `cbaa04179a99e7020f592ab1d9f8cdf893960df6`
- Target commit: `d58b2691233e4bcf5a803154f0e8ee1ca2558f8e`
- Relationship: target is a single-parent successor whose sole parent is base
- Applicable license: MIT; copied byte-for-byte as `environment/TotalControl/LICENSE`
- Runtime dependency boundary: RimWorld Core plus Harmony only

The target commit has exactly one parent and that parent is the specified base. The target About metadata declares RimWorld 1.6 support.

The production audit found: The target adds the vanilla quality fallback and pawn-kind gearHealthRange hit-point generation symmetrically for apparel and weapons. The starter contains the exact selected
base bytes and the oracle contains only the exact selected target bytes for the
listed production files. It does not delete implementation to create a no-op.

Source snapshot SHA-256:

- `Source/Patches/ApparelGenPatch.cs`: base `c8b8d9f2608ed1bc9dcb4ce94dd7d9714c185243f5fc2d42307a19f947db56d5`; target `2c9d5ab4bfb2236ba2228e370ac3ecbbfc2babd0d79fd6bd0d1c92fe3d81a309`
- `Source/Patches/WeaponGenPatch.cs`: base `50907f00e606293fff70d995e144d8733e22b06e04a40fa03793cefbd1a75cb1`; target `ae39332bd7cde69ba8a0c5c752a4db1a6b7621c19ae28829455881ddcf0c0fd7`
- applicable upstream license bytes: `4c7a76096097621ff71c65b0fbfae1f883800c5ff62679bbfc371f681f2027fb`

No upstream tests, bridge, save, fixture, binary, PDB, texture, sound, preview,
Workshop payload, runtime evidence, Steam data, or other asset was copied. The
benchmark-authored project, Support, verifier, Mod metadata, scripts, manifest,
and control plan are not represented as upstream files.

## Scored contract and private protocol

The scored production surface is `ApparelGenPatch and WeaponGenPatch gear construction`. `tests/assertions.json` is the
only maintained declaration of all 18 case IDs, fixtures,
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

A per-pawn PawnKindDef clone carries the health range; the original reference and range are restored. Temporary useHitPoints changes are observed and restored. Independent full Def lists and all original gearHealthRange/useHitPoints values are checked, and nested Rand tests remain.

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

- Reference (`solution/after` over the starter), `rhenium run` three times: `run-982b83ea17234882` (100, 18/18), `run-668bd15a15574a8e` (100, 18/18), `run-4f06591586f643ae` (100, 18/18); identical case outcomes.
- Unchanged starter, `rhenium run` `run-a8eaa4f9760646d5`: complete, score 10, 14 passed and 4 failed (`apparel-low-health`, `apparel-min-one-hp`, `weapon-low-health`, `weapon-min-one-hp`).
- Independently materialized starter (study control) `run-8f971105acbd42b3`: complete, 4 failed.
- E0 study controls and their outcomes: `private/study-controls/total-control-vanilla-gear-generation/NOTES.md`.
