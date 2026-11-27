# R⁴ source and runtime provenance

## Upstream source

- Repository: `https://github.com/CheaterEater-RM/RRRR`
- Tag: `v1.48`
- Target commit: `7fbf158f4b988a6f806cc609282175143a3a41a6`
- Starter/base commit: `db9e85bc758c402e53c55dd19ca8a588899f139c`
- License SPDX: `MIT`
- Copyright: `Copyright (c) 2026 CheaterEater`
- Target change: `v1.48: material basis for uncraftable gear + eligibility fixes`

The supplied authoring snapshot records the repository tag and commits above. This
Phase A-B authoring pass did not fetch the upstream repository and therefore did
not independently revalidate the complete tag/commit object graph. The starter
copies `Source/Utility/MaterialUtility.cs` from the recorded base commit and
supplies the recorded target commit's small `R4MaterialCostExtension.cs` contract
so the bounded task compiles. The oracle replaces both with the supplied target
versions. No other upstream code is graded. A future provenance decision that
depends on the complete upstream graph must collect fresh read-only evidence.

The upstream LICENSE says its MIT grant does not extend to textures containing
RimWorld art or other separately licensed textures. This snapshot therefore
contains only:

- the upstream MIT `LICENSE`;
- `Source/Utility/MaterialUtility.cs`;
- `Source/Defs/R4MaterialCostExtension.cs`.

It excludes `1.6/Assemblies/RRRR.dll`, every texture/image/preview, audio, Workshop
metadata/cache, and every RimWorld or Unity file. The private harness support files,
project files and Mod metadata are benchmark-authored and are not represented as an
upstream release snapshot.

Audited snapshot SHA-256 values:

- base `MaterialUtility.cs`: `44fdab7467d6e2a4127b63a553bd480122c34b714a5571f4750accff20a93000`;
- target `MaterialUtility.cs`: `e991f533730cb8b3eb6d78d8a948f04343df83b2f6706253a5300a91cf72efb5`;
- `R4MaterialCostExtension.cs`: `35c317b1bef1b4a0719fe0aa71533bb7fe7c912ecf0373d0df07ab798e63a746`;
- upstream `LICENSE`: `d9ee28c96b86b3595e4590b77720ac85c37c6fad824217a1b5946b1e1cc48e89`.

## Runtime pins

- RimWorld: `1.6.4871`
- Steam App: `294100`
- Steam public build: `23969874`
- Linux depot: `294103`
- Linux manifest: `3402513235443928324`
- Unity: `2022.3.35f1`, depot-provided Mono
- Runner: Linux x86_64 only
- SDK image: `mcr.microsoft.com/dotnet/sdk:8.0.422-bookworm-slim@sha256:63ebabdcde24cc8134304a6f50719cf1e22bb4e9f7148ac4ef967c7680187356`
- Compile target: `net472`
- Reference assemblies: `Microsoft.NETFramework.ReferenceAssemblies.net472` 1.0.3
- RimWorld compile-time API: `Krafs.Rimworld.Ref` 1.6.4871 (downloaded only while
  preparing the local evaluator image; not included in the pack or wheel)
- Harmony: library 2.4.2; Harmony Mod 2.4.2.0
- Harmony Mod archive SHA-256:
  `305d014d3ef893909e28ec48615b886c7ebfa3c71b40a45d45bc20bdd4713af1`

The exact Linux `Version.txt` revision and hashes of licensed files are intentionally
unrecorded until an authorized acquisition supplies them. Preparation must reject a
different first version token or missing runtime files. Evaluation runs with no
network and cannot acquire or repair the runtime.

## Private protocol v2

`tests/assertions.json` is the single maintained declaration for all 38 named
assertions, their fixtures, gate status, recorded scalar fields, expected facts,
expected material outputs, and the unchanged 10-point submission-shape plus
90-point engine weighting. The plugin validates it as
`rhenium-rimworld-private-v2`; the external supervisor reads expected results from
that manifest. Runtime preparation generates an adapter dispatch containing only
case IDs, fixture method references, and gate flags. The assertion manifest and
expected results are not copied to either candidate-readable image or mounted at
evaluation time.

The first two cases are runtime/definition and fixture-precondition gates. The
remaining cases cover the exact public resolver signature, adjusted craft and
stuff costs, authored-extension precedence, null/empty fallback boundaries, every
relevant technology tier, definition-versus-instance MarketValue, float32
nearest-even boundaries, and independent repair/clean settings and guards. The
rounding fixtures record actual definition MarketValue, selected bulk definition
MarketValue, the intermediate target, quotient, and float32 bits. Expected counts
come only from the private manifest, never from candidate output.

The scored scope is `ResolveMaterialBasis`, `GetRepairCycleCost`, and
`GetCleanCost`. Although the supplied target snapshot also changes
`DoRecycleProducts` and `SpawnPartialReclaim`, this version does not score their
random recovery, map placement, or eligibility behavior and does not claim to
restore or verify all of R⁴ v1.48.

## Planned real-game controls

The planned v2 control matrix is oracle 38/0 and base/no-op 7/31. Base and no-op
are expected to pass the two gates, the three craft-preservation cases, and the two
repair-guard cases. A missing public resolver reports `API_MISSING` only for its
independent contract case; it does not prevent the shared production entry points
from running. These counts are authoring expectations, not execution evidence.

This milestone has not acquired RimWorld and therefore has no oracle/base/nop
engine result. Old protocol evidence is not reusable. `validation/controls.json`
records the v2 not-run state explicitly. Do not promote the pack until oracle
passes and both independently materialized base and no-op controls complete and
fail the intended target behavior in the pinned runtime.

## Engine validation (2026-09-24)

This section supersedes the not-run statements above. Run through the Hub on one Linux x86_64 Docker host with the pinned RimWorld
1.6.4871 depot, networkless, after the verifier repairs recorded in
[the RimWorld support notes](../../../../../../docs/games/rimworld.md#engine-validation-2026-09-24).

- Reference (`solution/after` over the starter), `rhenium run` three times: `run-49c6888766274629` (100, 38/38), `run-38724cc02f5e4353` (100, 38/38), `run-452d4451b886430f` (100, 38/38); identical case outcomes.
- Unchanged starter, `rhenium run` `run-1eaeba110d2f43b8`: complete, score 10, 7 passed and 31 failed (`animal-basis`, `archotech-basis`, `authored-extension-used`, `clean-default`, `clean-ignores-repair-settings`, `clean-settings`, `definition-market-value`, `empty-cost-list-fallback`, `empty-extension-materials-fallback`, `industrial-components-stay-two`, `medieval-basis`, `negative-market-value`, `neolithic-basis`, `null-cost-list-fallback`, `null-extension-materials-fallback`, `positive-minimum-bulk`, `public-resolver-contract`, `repair-default`, `repair-ignores-clean-settings`, `repair-settings`, `round-even-above`, `round-even-below`, `round-even-half`, `round-odd-above`, `round-odd-below`, `round-odd-half`, `spacer-basis`, `spacer-components-stay-two`, `ultra-basis`, `undefined-basis`, `zero-market-value`).
- Independently materialized starter (study control) `run-70bd2683f585425d`: complete, 31 failed.
- E0 study controls and their outcomes: `private/study-controls/r4-uncraftable-material-basis/NOTES.md`.
