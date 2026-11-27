# Project RimFactory Revived source and validation provenance

## Exact public source audit

- Repository: `https://github.com/zymex22/Project-RimFactory-Revived`
- Starter/base commit: `6464e78a570914d0637157f3b55f48fa29f6b9d7`
- Target commit: `4950a19d60cf8305ebad472b8ec256429cd18b45`
- Relationship: target is a single-parent successor whose sole parent is base
- Applicable license: MIT; copied byte-for-byte as `environment/ProjectRimFactory/LICENSE`
- Runtime dependency boundary: RimWorld Core plus Harmony only

This task is the first authorized reserve. It replaces Automatic Outfit Manager:
the specified AOM base/target is a real single-parent production fix, but neither
commit tree contains a LICENSE or NOTICE, so the required compatible-license
bytes could not be preserved. No AOM source was copied.

The target commit has exactly one parent and that parent is the specified base. The target About metadata declares RimWorld 1.6 support.

The production audit found: The target disables the global temperature check, adds cell-local growth-season and vacuum conditions, and leaves blocker/seed behavior in place. The starter contains the exact selected
base bytes and the oracle contains only the exact selected target bytes for the
listed production files. It does not delete implementation to create a no-op.

Source snapshot SHA-256:

- `Source/ProjectRimFactory/CultivatorTools/Building_Cultivator.cs`: base `c3dc20a9bb83a35349268adcc302062e9af894b81a2fea6bb4561e8a5e3d6dab`; target `3876bd2f030854c3c7f45dd5885da0f8f7071a8ac0e3df53bdcef1da6e268a80`
- applicable upstream license bytes: `6fd82a094b92b574ae9fba95ead292ba191b6ce0922da883cd07552fb9e5e5a0`

No upstream tests, bridge, save, fixture, binary, PDB, texture, sound, preview,
Workshop payload, runtime evidence, Steam data, or other asset was copied. The
benchmark-authored project, Support, verifier, Mod metadata, scripts, manifest,
and control plan are not represented as upstream files.

## Scored contract and private protocol

The scored production surface is `Building_Cultivator.TryPlantNew`. `tests/assertions.json` is the
only maintained declaration of all 12 case IDs, fixtures,
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

Independent snapshots cover environmental flags, placement counters and seed-service settings. Owned Harmony patches are removed and their ownership is checked after every case, including partial installation failures.

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

## Engine validation (2026-09-24)

This section supersedes the not-run statements above. Run through the Hub on one Linux x86_64 Docker host with the pinned RimWorld
1.6.4871 depot, networkless, after the verifier repairs recorded in
[the RimWorld support notes](../../../../../../docs/games/rimworld.md#engine-validation-2026-09-24).

- Reference (`solution/after` over the starter), `rhenium run` three times: `run-52b63ba3dc314278` (100, 12/12), `run-bf2e3b808a0348ae` (100, 12/12), `run-6be50b7d8ce34bee` (100, 12/12); identical case outcomes.
- Unchanged starter, `rhenium run` `run-01b7a4d9fdb147da`: complete, score 10, 9 passed and 3 failed (`local-season-rejects`, `vacuum-boundary-rejects`, `vacuum-sensitive-rejects`).
- Independently materialized starter (study control) `run-50d6552d51464c62`: complete, 3 failed.
- E0 study controls and their outcomes: `private/study-controls/project-rimfactory-cultivator-environment/NOTES.md`.
