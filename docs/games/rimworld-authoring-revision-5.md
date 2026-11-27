# RimWorld catalog 0.3.4 / Adaptive Storage build compatibility

Date: 2026-10-26. Status: **reference compilation passed on macOS arm64;
Linux image and real-engine validation unrun**. This is repository maintenance,
not an exam attempt or a new task. It follows the user's decision to repair
Adaptive Storage before considering replacement.

## Scope and version decision

Catalog 0.3.3 advances to 0.3.4; only Adaptive Storage advances from authoring
revision 4 to 5. The task count, public exam, 15-case protocol-v3 manifest, 10/90
weights, scored slot-limit behavior and mutation expectations are unchanged.
ThingClass source and the historical base/reference transition are unchanged.
This is a build/delegation compatibility patch, with no CLI/API/schema break.
Other tasks' existing control records retain their original catalog identities.

Three lambda transformations change both starter and reference source identity;
the Support change affects both candidate compilation and adapter identity.
Existing role images and results for different inputs must not be relabeled or
reused. Independent source hashes, fresh assembly hashes and an evaluation identity
are still required by the existing runtime contracts. No release or push was made.

No task was added, removed, renamed or changed in catalog metadata.

## Fixed SDK compatibility

An official SDK 8.0.422 macOS arm64 binary archive was SHA-512 checked against
Microsoft's release metadata and unpacked only into temporary task state. No
host installer, system package manager or global runtime configuration was used.
The SDK image, C#12, net472, package versions/content hashes, overflow mode and
unsafe settings are unchanged.

Before the repair, an independently materialized reference reproduced CS1001 at
StorageRenderer.cs lines 241, 274 and 343. The source used C#14 lambda parameters
with an `in` modifier but no explicit types. Both source trees now explicitly
type every parameter, including the DrawPhase/int/SectionLayer context and
`in TransformData`. Bodies, static capture behavior and delegate passing remain
unchanged. No preview compiler or newer SDK was substituted.

Source derivation and dependency inventories retain the original upstream
hashes and add three exact single-occurrence transformations and output hashes.
Both NOTICE files describe the additional adaptation, and their inventory hashes
are updated. The existing replay test reverses all adaptations, verifies the
fixed upstream hashes, and reconstructs both source trees without a network.

## Rectangle delegation

The thin authored StorageCellRect wrapper now enumerates `CellRect.Cells`, the
public enumerable, instead of selecting the struct's pattern enumerator through
`foreach (IntVec3 cell in cells)`. Constructor, Area and Contains still delegate
to the public game API. No excluded Verse-derived implementation was copied.

The verifier remains byte-identical: it still compares coordinates, enumeration,
area and containment, including the zero-width case. No failing gate or expected
value was removed. The change aligns the wrapper's enumerable route with the
game's enumerable contract, but its effect on the previously reported real-game
gate failure remains **unvalidated** without the pinned game. Compilation cannot
prove runtime enumeration semantics or complete initialization.

## Verification and remaining acceptance gates

Fresh independent base, reference and no-op candidates and their corresponding
verifiers passed locked restore and reference compilation with SDK 8.0.422 on
macOS arm64. Every candidate build had zero errors and 560 upstream warnings;
every verifier build had zero errors and warnings. controls.json records the
curated assembly hashes and retains the previous failed-compilation history.
Full command logs and build products remain in local task state outside the pack.

The RimWorld CI job now uses exactly SDK 8.0.422 and invokes the existing compile
runner for all three controls. It exercises the actual source graphs and verifiers
without acquiring a game. That Linux CI job has not been executed in this chat.

From a configured repository environment, use a fresh state destination:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:plugins/rimworld/src \
  .venv/bin/python \
  benchmarks/rimworld-core/private/harbor/adaptive-storage-slot-limit-restore/validation/reference_compile.py \
  /absolute/new/task-state/reference-compile --dotnet /existing/path/to/dotnet
```

The runner refuses an existing output or a mismatching SDK. A successful compile
is not a full benchmark result. The current Mac has no Docker or licensed,
controlled Linux x86_64 environment, and the user has no such host available.
No Linux builder/evaluator image was rebuilt and no real-game control ran.
All 15 engine assertions and all mutation outcomes remain unrun for these inputs.
The integration stays In Development and this task is not accepted for full use.

On an authorized Linux x86_64 host, the remaining work is to use the normal
explicit Steam acquisition/runtime-prepare workflow, build matching immutable
role images, verify their exact input identities, then run the reference, base,
independent no-op and declared mutation controls through the Hub. The reference
must pass every case; base/no-op must complete and fail for the intended slot
regression; fixture failures must stay incomplete. The public manifest must not
be weakened if further runtime defects appear.

## Repository check results (2026-10-26)

The host has no devenv executable. Equivalent checks used a fresh Python 3.12
environment synchronized with `uv sync --locked --all-packages --all-extras` in
temporary task state. The original checkout and virtual environment were not
replaced. Frontend package.json and package-lock.json matched the existing
dependency installation byte-for-byte; those dependencies were reused for checks.

| Check | Observed result |
| --- | --- |
| Original reference, pinned SDK 8.0.422 | Reproduced the three CS1001 errors |
| Repaired base/reference/no-op and matching verifiers | All six assemblies compiled; sources/locks/adapter bytes and assembly hashes rechecked |
| RimWorld Python suite | 232 passed |
| Ruff, src/plugins/providers/tests | Passed |
| Mypy, src/plugins/providers/tests | Passed, 258 source files |
| Full Python suite, fresh locked environment | 2026 passed, 7 failed, 28 skipped, 2 warnings |
| Frontend lint | Passed with existing warnings |
| Frontend tests | 1 passed |
| Frontend production build | Passed; tracked dist/.keep preserved |
| Required shell entry points, Bash syntax and ShellCheck 0.11.0 | Passed |
| CI YAML parse and pinned compile step | Passed local inspection; remote CI unrun |
| git diff --check | Passed |
| Linux role images and real-game assertions/mutations | Unrun: controlled licensed Linux x86_64 Docker host unavailable |

The seven full-suite failures are outside the changed implementation:

- `tests/test_slay_the_spire_native_assets.py::test_native_task_bytes_match_measured_manifest`
  for `stslib-block-ledger-r1` and `stslib-icon-layout-r1`: asset files are still Git
  LFS pointers, and git-lfs is not installed; measured byte hashes therefore differ.
- `tests/test_util_hash_tree.py::test_matches_reference_on_adversarial_tree`,
  `test_matches_reference_with_symlinks`, and `test_root_variants_match_reference`:
  their adversarial fixture collides on this case-insensitive macOS filesystem.
- `plugins/mindustry/tests/test_mindustry_construct_runtime_builder.py::test_prepare_builds_from_acquired_source`
  and `plugins/terraria/tests/test_terraria_runtime_builder.py::test_prepare_builds_task_image_from_recorded_source`:
  their existing paths reach the unavailable Docker CLI.

Those files, fixtures, frozen manifests and implementations were not changed to
make checks pass. A separate existing RimWorld sandbox-command test also reached
real Docker cleanup after faking container execution; the unchanged HEAD test
reproduced that defect. It now supplies an explicit absent-container inspection
response, keeping the unit test independent of Docker without changing production
cleanup or its existing behavior tests.

The 28 skips comprise two filesystem capability cases, three unavailable DST
server cases, seven native Windows Balatro cases, nine unavailable GMod/Linux
runtime or controlled-audit cases, one unavailable Palworld server case, and six
missing javac 21+ cases. They are not evidence for those platforms or engines.
This check run contains no real RimWorld evidence. The task remains blocked for
full acceptance, and the repository-wide test suite is not green on this host.
