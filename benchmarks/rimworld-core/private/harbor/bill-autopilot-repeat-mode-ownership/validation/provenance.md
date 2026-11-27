# Bill Autopilot source and validation provenance

## Exact public source audit

- Repository: `https://github.com/vbardales/Rimworld-Bill-Autopilot`
- Starter/base commit: `7c36614cb420b40068b67ea9b9b2225c01cdc06a`
- Target commit: `61e6b2fe67dff6296de63383d8d92ad78077d5f5`
- Relationship: target is a single-parent successor whose sole parent is base
- Applicable license: MIT; copied byte-for-byte as `environment/BillAutopilot/LICENSE`
- Runtime dependency boundary: RimWorld Core plus Harmony only

The target commit has exactly one parent and that parent is the specified base. The target About metadata declares RimWorld 1.6 support.

The production audit found: The target records foreign mode identity, routes readiness through that mode's ShouldDoNow, and prevents Autopilot drift capture from claiming modes it does not own. The starter contains the exact selected
base bytes and the oracle contains only the exact selected target bytes for the
listed production files. It does not delete implementation to create a no-op.

Source snapshot SHA-256:

- `Source/Runtime/AutoBillSync.cs`: base `40ee5323b8eac98cb2dad194b4598f2eb6ed6d111cde3daed981e0aeb6792420`; target `958d89377c714cbdd3575d1a5eec8a6e4c46760a9b6c4590581dca19ebae810c`
- `Source/Runtime/BillMemory.cs`: base `2e890714c4b567c8c9872b25a0d642d938259224332d04742e9a0a88dbc2debe`; target `953229961b462843805db6761b948eb50a9afe0d3ede8bfe53f3644c002e8f6e`
- `Source/Runtime/RecipeProbe.cs`: base `a2016b492032bba7081b9d3ed016b57c97c1c9b1fba4c922c5aecb6224a63695`; target `6ae5480e5d486fbef7823815b9beefad867589959879466838e356a41403fafd`
- applicable upstream license bytes: `1a24db0b016bf77e6d15fda1bf27b20c76f9b14f1a21458ba36f2bb3a7d2c908`

No upstream tests, bridge, save, fixture, binary, PDB, texture, sound, preview,
Workshop payload, runtime evidence, Steam data, or other asset was copied. The
benchmark-authored project, Support, verifier, Mod metadata, scripts, manifest,
and control plan are not represented as upstream files.

## Scored contract and private protocol

The scored production surface is `AutoBillSync, BillMemory, and RecipeProbe repeat-mode lifecycle`. `tests/assertions.json` is the
only maintained declaration of all 17 case IDs, fixtures,
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

BillNamePersisted, LinkedGroupPersisted and MemoryRoundtrip now read from a fresh BillMemory created by a real Scribe deep load. A separately persisted sentinel validates the Scribe transport; missing candidate fields remain production mismatches. A legacy XML case removes optional fields before loading and checks null/empty/default compatibility. Save files are in a unique /tmp/rhenium-scribe-* directory in the task container tmpfs, never the pack. Probe state, patches, Scribe mode and temporary files are restored and checked.

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

- Reference (`solution/after` over the starter), `rhenium run` three times: `run-b0b9af2e411c4533` (100, 17/17), `run-f7acecdd3b194b71` (100, 17/17), `run-a1f126612b8a4e7c` (100, 17/17); identical case outcomes.
- Unchanged starter, `rhenium run` `run-6e13dc05026a491b`: complete, score 10, 11 passed and 6 failed (`foreign-mode-recognized`, `foreign-mode-remembered`, `foreign-mode-restored`, `foreign-should-do-now-false`, `foreign-should-do-now-true`, `memory-roundtrip`).
- Independently materialized starter (study control) `run-31ab3141c6ff42ef`: complete, 6 failed.
- E0 study controls and their outcomes: `private/study-controls/bill-autopilot-repeat-mode-ownership/NOTES.md`.
