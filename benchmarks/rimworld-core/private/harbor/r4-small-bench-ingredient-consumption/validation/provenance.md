# R⁴ source and validation provenance

## Exact public source audit

- Repository: `https://github.com/CheaterEater-RM/RRRR`
- Starter/base commit: `40daa82d0bcc65d6542a6acb81515e808f6d4184`
- Target commit: `259c5d3992b2603b1a07e8d3db4b2446140874df`
- Relationship: target is a single-parent successor whose sole parent is base
- Applicable license: MIT; copied byte-for-byte as `environment/R4/LICENSE`
- Runtime dependency boundary: RimWorld Core plus Harmony only

The target commit has exactly one parent and that parent is the specified base. The target About metadata declares RimWorld 1.6 support.

The production audit found: The target factors per-cell consumption and adds the radial fallback used when vanilla places ingredients beside a one-cell bill giver. The starter contains the exact selected
base bytes and the oracle contains only the exact selected target bytes for the
listed production files. It does not delete implementation to create a no-op.

Source snapshot SHA-256:

- `Source/Utility/MaterialUtility.cs`: base `3bc706b83b4234a6f9ff4c6368a0d2cc6624e8b73acb1773a085fd6e9927fd61`; target `9f13adbfc1e21220cc90942408c26fbcf001cc3998a0e2c302f501a2b47a98a0`
- applicable upstream license bytes: `d94dffcf4684d8dc6f9a0f0b1c18696d8be625a21c0940c037d042daf2160f66`

No upstream tests, bridge, save, fixture, binary, PDB, texture, sound, preview,
Workshop payload, runtime evidence, Steam data, or other asset was copied. The
benchmark-authored project, Support, verifier, Mod metadata, scripts, manifest,
and control plan are not represented as upstream files.

## Scored contract and private protocol

The scored production surface is `MaterialUtility.ConsumeIngredientsOnBench`. `tests/assertions.json` is the
only maintained declaration of all 16 case IDs, fixtures,
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

A private Map/grid is owned per fixture. Registered things and edifices are removed; every cell in both grids is scanned after cleanup, including objects not in the callback inventory.

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

- Reference (`solution/after` over the starter), `rhenium run` three times: `run-d5cd9fa7aa0743c3` (100, 16/16), `run-cbcbdf8df90f4f0d` (100, 16/16), `run-5992b56afd4e46b5` (100, 16/16); identical case outcomes.
- Unchanged starter, `rhenium run` `run-fdbc4769d7244f5c`: complete, score 10, 10 passed and 6 failed (`duplicate-costs-aggregate`, `interaction-cell-origin`, `multiple-stacks-exact`, `partial-stack-preserved`, `radius-boundary-included`, `small-bench-adjacent`).
- Independently materialized starter (study control) `run-8a61e2220042417a`: complete, 6 failed.
- E0 study controls and their outcomes: `private/study-controls/r4-small-bench-ingredient-consumption/NOTES.md`.
