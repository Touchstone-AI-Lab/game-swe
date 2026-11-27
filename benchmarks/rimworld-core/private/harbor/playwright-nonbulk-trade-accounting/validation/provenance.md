# Playwright source and validation provenance

## Exact public source audit

- Repository: `https://github.com/morerokk/Rimworld-Playwright`
- Starter/base commit: `11fa563967cf368e00f5011d79c9f9476019edb2`
- Target commit: `f518aed8a2f2899c4e3c38a942685b7947eaeea7`
- Relationship: target is a single-parent successor whose sole parent is base
- Applicable license: MIT; copied byte-for-byte as `environment/Playwright/LICENSE`
- Runtime dependency boundary: RimWorld Core plus Harmony only

The target commit has exactly one parent and that parent is the specified base. The target About metadata declares RimWorld 1.6 support.

The production audit found: The target adds a Harmony prefix state snapshot and uses it in the postfix instead of reading a tradeable after non-bulk colony items may have been removed. The starter contains the exact selected
base bytes and the oracle contains only the exact selected target bytes for the
listed production files. It does not delete implementation to create a no-op.

Source snapshot SHA-256:

- `Source/Playwright/Patches/TradeablePatches.cs`: base `81196772511b2ac722dbff465d75900adae2375ac0e812e58fd799347cb9e021`; target `84022baa6ac226a076d0a6924139bf0fb9527181ae39b7c948b70e8735d53ac4`
- applicable upstream license bytes: `2406e3c1eb097fae75b2bf8aa408604181720b3bed452c5d34abccfdf0fe3add`

No upstream tests, bridge, save, fixture, binary, PDB, texture, sound, preview,
Workshop payload, runtime evidence, Steam data, or other asset was copied. The
benchmark-authored project, Support, verifier, Mod metadata, scripts, manifest,
and control plan are not represented as upstream files.

## Scored contract and private protocol

The scored production surface is `Tradeable_ResolveTradePatches Prefix/Postfix`. `tests/assertions.json` is the
only maintained declaration of all 14 case IDs, fixtures,
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

Independent snapshots cover trade action, things/definition/count, scenario and TradeSession.trader. Owned Harmony patches are removed and observed after each case; restored values remain checked at later case boundaries.

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

- Reference (`solution/after` over the starter), `rhenium run` three times: `run-668675cce8b248b4` (100, 14/14), `run-5fbff2f37d2f4d8d` (100, 14/14), `run-f948c42e65b749ae` (100, 14/14); identical case outcomes.
- Unchanged starter, `rhenium run` `run-f094d90a0f154091`: complete, score 10, 8 passed and 6 failed (`definition-preserved-after-resolve`, `empty-tradeable-not-counted`, `nonbulk-sale-captured`, `nonbulk-sale-counted`, `purchase-not-counted`, `zero-transfer-not-counted`).
- Independently materialized starter (study control) `run-a3ce7c69899a415c`: complete, 6 failed.
- E0 study controls and their outcomes: `private/study-controls/playwright-nonbulk-trade-accounting/NOTES.md`.
