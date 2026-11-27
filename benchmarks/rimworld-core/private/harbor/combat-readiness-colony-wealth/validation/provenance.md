# Combat Readiness Check source and validation provenance

## Exact public source audit and 1.6 reconstruction

- Repository: `https://github.com/emipa606/CombatReadinessCheck`
- Selected historical base: `67f2446e4e6a3d38f7ac3b90c923f4967ee29f86`
- Selected historical target: `f9b83ce14d9147510969878ff1bf96ed55d99544`
- Historical relationship: the target has exactly one parent, and that parent is
  the selected base
- Audited 1.6 descendant: `a3c1cd53260bbb74c8e3ce9e3cd012264c1758bb`
- Lineage: the selected target is an ancestor of the audited descendant, six
  commits behind it
- Applicable license: MIT at base, target, and audited 1.6 descendant; copied
  byte-for-byte as `environment/CombatReadinessCheck/LICENSE`
- Runtime dependency boundary: RimWorld Core plus Harmony only

The historical pair predates the RimWorld 1.6 port, so its bytes are not falsely
presented as 1.6 source. The selected target fixes production behavior by letting
vanilla handle non-home and fixed-wealth states, then returning raw armoury wealth
plus the configured building-wealth share instead of running both values through
the incident-points curve.

The audited 1.6 descendant declares RimWorld 1.6 and Harmony as its sole hard Mod
dependency. Its selected target file retains that fix. Relative to the historical
target, the only live-code change in that file is the mechanical settings API
rename from `CRC_Loader.settings.percentOfValueForBuildings` to
`CRC_Loader.Settings.PercentOfValueForBuildings`; the remaining change deletes
unreachable comments.

The oracle is therefore the exact selected file bytes from audited 1.6 commit
`a3c1cd53260bbb74c8e3ce9e3cd012264c1758bb`. The starter is a documented 1.6
reconstruction of the historical base's scoring-relevant production behavior: it
retains home-map interception, curve-transforms both wealth components, and
applies the same building percentage using the current settings names. Historical
diagnostic logging and its eager parent-label read were excluded because the
selected 1.6 target removed that dead branch and it is outside the scored wealth
contract. This is not described as byte-identical upstream base source.

Source snapshot SHA-256:

- historical base file bytes: `436afbabaaacf3342c6a840ad87bbacae699a625e255bb1b1198f0b5a02d3d84`
- historical target file bytes: `24105820c36ecb0dd4d3b4dda28882404d9d9235d4b91448a66fc893681338d8`
- reconstructed 1.6 starter file:
  `118411801616bdc9bd233fba223b606a8cc42513c478badd8477d9f14c28b21e`
- exact audited 1.6 oracle file:
  `69d0d4afe5e9500e36fac1a590b806f8011774797db475f368b0e5b14d124431`
- applicable upstream license bytes:
  `b93b4ab4758761c1f6c02e7bd2b6ef7b0ea8491a23c122040533a11de29e4023`

No upstream test, bridge, save, fixture, binary, DLL, PDB, texture, sound,
preview, Workshop payload, runtime evidence, Steam data, or other asset was
copied. The project, Support, verifier, Mod metadata, scripts, assertion manifest,
and control plan are benchmark-authored.

## Scored contract and private protocol

The scored production surface is
`CRC_Reintegrated.MarvsMapWealthForStoryTeller.Prefix`. The manifest at
`tests/assertions.json` is the only maintained declaration of all 16 case IDs,
fixtures, expected observations, gate flags, and the 10/90 weighting. Protocol v3
exists explicitly for per-task assertion counts and does not reuse the legacy R4
protocol-v2 evidence identity. Runtime preparation generates only dispatch
metadata. Expected observations and the manifest do not enter the candidate
source workspace, builder input, or evaluation mount.

The fixtures cover runtime/state gates, vanilla pass-through states, raw component
accounting, zero/full/fractional/out-of-range percentage boundaries, and two
negative controls that preserve home-map interception and one armoury query. Each
fixture restores task-owned settings and observation state; the common harness
also restores RimWorld Rand state. A gate failure makes evidence incomplete. A
completed production mismatch remains complete and failed.

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
task. Compile, container, and licensed engine work belong to a later independent
validation pass.

## Authoring revision 2 fixture contract

Independent snapshots cover home/wealth/storyteller inputs, configured percentage, armoury inputs and call counters. Owned Harmony patches are removed and observed after each case. The historical reconstruction and 1.6 descendant provenance above is unchanged.

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

- Reference (`solution/after` over the starter), `rhenium run` three times: `run-39bcdda283da4d58` (100, 16/16), `run-3115c73ac20f464b` (100, 16/16), `run-09d77c4ad0d34a54` (100, 16/16); identical case outcomes.
- Unchanged starter, `rhenium run` `run-7f8eb9890b054399`: complete, score 10, 5 passed and 11 failed (`above-full-percentage-preserved`, `armoury-wealth-stays-raw`, `building-percentage-stays-raw`, `fixed-wealth-passes-through`, `fixed-wealth-skips-armoury`, `fractional-building-percentage`, `full-building-percentage`, `nonhome-map-passes-through`, `wealth-components-add`, `zero-building-percentage`, `zero-components-remain-zero`).
- Independently materialized starter (study control) `run-897aca78f1814eb8`: complete, 11 failed.
- E0 study controls and their outcomes: `private/study-controls/combat-readiness-colony-wealth/NOTES.md`.
