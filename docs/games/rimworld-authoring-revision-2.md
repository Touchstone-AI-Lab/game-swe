# RimWorld catalog 0.3.1 / authoring revision 2

This revision is repository maintenance and authorized benchmark authoring.
It preserves the public production goals and 10/90 weights. It is **Draft-only**:
Adaptive Storage's full-source compile closure remains blocked, and no C#
reference compilation, container, engine, oracle/base/nop or mutation control
has run. Python/fake results are not evidence of C# behavior.

## Version and evidence review

The catalog changes from 0.3.0 to 0.3.1; each of the nine new task.toml files
records `authoring_revision = 2`. There is no CLI/API/database/schema change and
no new wire protocol. v3 already supports dynamic counts and two gates. Its
manifest validator now requires the two gates to bracket every behavior case.
This rejects the defective early cleanup gate instead of generating an adapter
that never checks the completed fixtures. The old R4 v2 task, its 38 cases and
its manifest bytes are untouched; its task/control metadata still records the
original authoring catalog.

| Task | Assertions (before → after) | Authored change |
| --- | --- | --- |
| r4-small-bench-ingredient-consumption | 16 → 16 | Entire private grids checked after removal |
| project-rimfactory-cultivator-environment | 12 → 12 | Settings/counters and Harmony ownership restored per case |
| adaptive-storage-slot-limit-restore | 12 → 12 | Full upstream source restored; instance snapshots; **closure unresolved** |
| combat-readiness-colony-wealth | 16 → 16 | Independent wealth/settings/counter and patch snapshots |
| customize-weapon-ability-tracker | 16 → 18 | Equipment lifecycle, Scribe, holder update and PostLoadInit controls |
| total-control-vanilla-gear-generation | 18 → 18 | PawnKindDef clone, useHitPoints and Rand restoration |
| bill-autopilot-repeat-mode-ownership | 16 → 17 | Real Scribe round trips and missing-field compatibility |
| playwright-nonbulk-trade-accounting | 14 → 14 | TradeSession/scenario/static state and patch ownership |
| zombieland-dynamic-needs-capacities | 14 → 19 | Reproducible source slice; benefit/pain branch controls and set restoration |

Each tests/assertions.json remains the sole case-ID, fixture, expected, gate and
weight declaration. No expected-value table is compiled or mounted in the
candidate process. Dispatch is still generated from the manifest. Control
matrices are authoring expectations, never observed scores. New controls link to
manifest case IDs instead of defining another rubric.

All nine rubric hashes change because their ordered gate plans change. Support,
Verifier and generated dispatch are already included in task-scoped adapter/build
hashing. Restored Adaptive Storage and sliced Zombieland also change task-source
identity. Catalog identity changes globally, so even legacy task observations
cannot be relabeled as current catalog evidence. Old immutable images are not
rewritten; preparation must later produce new content-bound role images and
artifacts. Evaluation continues to reject old/mismatched source, rubric, adapter,
image, task or protocol evidence. No old evidence was migrated or reused.

There is no public contract migration requiring a breaking CLI/API commit footer.
Operators must re-materialize revision-2 attempts and, only in a separately
authorized validation session, prepare new artifacts. A 0.3.0 v3 pack with the
invalid early gate is intentionally rejected by the strengthened authoring
validator. Do not patch old evidence to match the new hashes.

## Source closure and provenance

Adaptive Storage initially had a 104-line compiled reconstruction and separate
796-line uncompiled `ThingClass 2.cs` copies. The short version deleted real
production behavior and replaced Notify_SettingsChanged with an empty method.
The canonical base and oracle now contain the complete audited upstream files;
the user's duplicate files remain untouched and excluded from compilation.

The actual upstream dependency/access requirements are larger than the declared
project: Fishery and ModCompatibility, ITransformable/TransformData,
GraphicsDef/StorageCell/ThingCollection/StorageRenderer, quality/cell-table
bookkeeping, global usings, net48/PolySharp and Publicizer access (including
MapDrawer.sections). Supplying empty names or deleting those paths is not an
acceptable closure. No such source or dependency was fabricated. The exact
read-only source URLs, commits, hashes and unresolved access boundary are in the
[task provenance](../../benchmarks/rimworld-core/private/harbor/adaptive-storage-slot-limit-restore/validation/provenance.md).
This task still requires a source-preserving closure decision and implementation.

Zombieland retains the unchanged bodies and Harmony attributes of three selected
patch classes. The whole-Mod static initializer (PatchGroups, Twinkie assets,
optional integrations and CrossPromotion) is excluded. This is explicitly a
source slice, not byte-exact whole-file upstream. The generator accepts only the
pinned upstream SHA-256, validates retained blocks and output hash, and forbids
in-pack output. Base and target were independently reproduced in temporary state.
The upstream MIT license is retained. `ZombieSymbiant` in Support is a clearly
identified authored boundary for external linked-host benefit inputs; it does
not implement the scored need, capacity or pain calculations. Complete symbiosis
linkage itself is not validated. See the [derivation record](../../benchmarks/rimworld-core/private/harbor/zombieland-dynamic-needs-capacities/validation/source-derivation.json)
and [generator](../../benchmarks/rimworld-core/private/harbor/zombieland-dynamic-needs-capacities/validation/slice_source.py).

Combat Readiness's historical fix, six-commit 1.6 descendant and reconstructed
base distinctions remain unchanged; no historical file is relabeled as an exact
1.6 snapshot. No licensed binary, save, asset, SDK, provider state or token was
added. The only new C# peripheral stub is the authored ZombieSymbiant boundary;
all shared fixture/Scribe/state helpers are benchmark-authored infrastructure.

## Persistence, lifecycle and integrity controls

BillMemory is deep-saved and loaded into a different instance in actual Scribe
contexts. A separate persisted transport sentinel detects an invalid fixture.
Candidate name, foreign repeat-mode string and linked group are read only from
the loaded instance. Missing legacy fields are removed from task-owned temporary
XML before loading. Unresolved repeat modes also go through AutoBillSync.Create.

Customize Weapon creates a real weapon with provider/equippable comps and a
Pawn_EquipmentTracker holder. AddEquipment, SetOrUpdateAbilities and Remove invoke
actual public lifecycle entry points. Private SyncAbilities is never called by
the fixture. A fresh Scribe deep-loaded envelope constructs a different provider,
executes PostExposeData and PostLoadInit, then uses the public post-load update.
A seeded managed set makes a deleted PostLoadInit clear observable. The reload
case calls ReloadFrom and observes charges plus ammo consumption.

All nine tasks now retain cleanup audits until the terminal gate. Per-instance
restoration obligations are declared at mutation sites and compared with actual
registrations, so another callback cannot conceal a missing registration. Independent
boundary snapshots are checked before and after behavior cases, including global
Def lists/ranges/flags and task-specific static state. Cleanup failure poisons the
run instead of disappearing when the callback list is cleared. Per-case Game
ownership isolates generated IDs. Rand compressed state and stack depth are
compared around PushState/PopState. Missing reflection/API access fails closed.
Objects/grids/holders created by individual tasks remain covered by retained
state checks. The bootstrap also has the missing StaticConstructorOnStartup
attribute so the private verifier can actually be scheduled.

Ordinary completed candidate observations and explicitly wrapped candidate
exceptions are graded as complete mismatches. Setup, Scribe transport, missing
fixture APIs, restoration, global-state or protocol failures produce incomplete
evidence. The external supervisor still rejects unknown/duplicate/missing/extra
cases, unknown fields, duplicate JSON keys, malformed JSON, non-finite values and
multiple terminals. These checks were not weakened.

## Required later two-way validation (all not-run)

1. Resolve Adaptive Storage's dependency and private-access closure while keeping
   the complete production methods. Reference-compile base and oracle for every
   task against the declared pinned game/Harmony/framework references. Verify
   callback signatures, accessibility, Rand.StateCompressed/stateStack,
   DefDatabase.Remove, Scribe deep-load constructors, equipment notifications,
   Game/ID-manager initialization, and absence of optional-Mod/asset startup.
2. In a separately authorized licensed environment, build distinct immutable
   per-task builder/evaluator roles. Run all current manifest cases in real
   RimWorld for oracle, independently materialized base and nop controls.
   Oracle must pass every required case; base/nop must fail the intended behavior
   and still complete, except an actual fixture/build/runtime failure which must
   remain incomplete. Reconcile planned counts with observed evidence honestly.
3. Apply the single-site mutants in Bill and Customize Weapon
   `validation/mutation-controls.json` to oracle copies in owned temporary state.
   Removing each Scribe call, equip synchronization, holder resolution, state
   serialization or PostLoadInit clearing must fail the linked manifest case(s),
   while the unchanged oracle passes. These are **authoring expectations**;
   the source mutation plans are not executed proof.
4. For every task, omit a restoration registration, leave each listed invariant
   changed, introduce an unregistered grid/Def/member, throw during restore and
   leave an extra Rand push. Each must yield incomplete; ordinary completed
   production mismatches must remain complete=true, passed=false.
5. Confirm pack bytes remain read-only, saves stay in task tmpfs, and stale or
   cross-task image/artifact/evidence identities are refused. No public support
   or benchmark pass claim is appropriate before these checks succeed.

## Safe local checks performed in this session

The existing Python 3.12 environment was used without installation. Source paths
and mini-swe-agent configuration were redirected to isolated temporary state.
The available `devenv` command was absent; direct installed tools were used.
Ruff and Mypy passed. Full safe pytest passed after reading and explicitly
excluding the one DST test that would launch a discovered real headless server.
No real engine was started. Precise counts and final file hashes are in the local
handoff audit; synthetic/fake tests are labeled as such. A RimWorld wheel was
built offline in temporary state and inspected for package contents; that does
not validate C# or engine behavior. ShellCheck was unavailable and not installed.
