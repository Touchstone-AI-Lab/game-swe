# Customize Weapon source and validation provenance

## Exact public source audit

- Repository: `https://github.com/realloon/CustomizeWeapon`
- Starter/base commit: `47cf5e74ab3764242c1fbd833a97cba122c77f1e`
- Target commit: `37c7140e2b7d6211f0cd6bfa6ed381705b090c81`
- Relationship: target is a single-parent successor whose sole parent is base
- Applicable license: MIT; copied byte-for-byte as `environment/CustomizeWeapon/LICENSE`
- Runtime dependency boundary: RimWorld Core plus Harmony only

The target commit has exactly one parent and that parent is the specified base. The target About metadata declares RimWorld 1.6 support.

The production audit found: The target centralizes lazy tracker creation and managed synchronization, adds empty fast paths, and repairs equip/unequip/post-load state transitions. The starter contains the exact selected
base bytes and the oracle contains only the exact selected target bytes for the
listed production files. It does not delete implementation to create a no-op.

Source snapshot SHA-256:

- `Source/ThingComps/CompAbilityProvider.cs`: base `d24b82c8db2a663161e1d6691675b46a23e2adfbe161f5afc6327d53b46e330d`; target `c1d6358828bc2e76f24bc93238775a95921813242f526cd68918bd2c689a78f7`
- applicable upstream license bytes: `deb6a149028b58c009caafe4dd2de2c45df78b28fcfb73c66c06a0ea7fc78ee7`

No upstream tests, bridge, save, fixture, binary, PDB, texture, sound, preview,
Workshop payload, runtime evidence, Steam data, or other asset was copied. The
benchmark-authored project, Support, verifier, Mod metadata, scripts, manifest,
and control plan are not represented as upstream files.

## Scored contract and private protocol

The scored production surface is `CompAbilityProvider managed ability lifecycle`. `tests/assertions.json` is the
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

A real ThingWithComps with CompEquippable and candidate provider is added to and removed from Pawn_EquipmentTracker. No private SyncAbilities invocation remains. Empty management, no holder, unrelated ability, duplicate props, removal, charges, cooldown, stale state and actual ReloadFrom are retained. Holder updates and PostLoadInit clearing have separate cases. A real Scribe deep save/load creates a new envelope, pawn, equipment and provider, calls PostExposeData through loading and PostLoadInit, and then the public SetOrUpdateAbilities entry. Def registration, holder/ability state, Scribe mode and temp files have restoration observations.

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

- Reference (`solution/after` over the starter), `rhenium run` three times: `run-169880b19aff4131` (100, 18/18), `run-ef338d8f840b44bb` (100, 18/18), `run-95ca3d9298e6484b` (100, 18/18); identical case outcomes.
- Unchanged starter, `rhenium run` `run-3c5d095073dc4769`: complete, score 10, 14 passed and 4 failed (`duplicate-props-deduplicated`, `holder-update-adds-ability`, `managed-ability-added`, `missing-tracker-created`).
- Independently materialized starter (study control) `run-b768928ac41a466c`: complete, 4 failed.
- E0 study controls and their outcomes: `private/study-controls/customize-weapon-ability-tracker/NOTES.md`.
