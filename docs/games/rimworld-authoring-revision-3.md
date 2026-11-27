# RimWorld catalog 0.3.2 / authoring revision 3

This is repository-maintenance authoring, not benchmark execution evidence.
The pack remains **Draft-only**. Adaptive Storage has a partial source closure
and is still blocked. No C# compilation, container, engine or C# mutation control
was run for this revision.

## Version and evidence decision

Catalog 0.3.1 → 0.3.2; the nine new tasks advance together from authoring revision
2 → 3. This patch corrects fixture failure classification and adds dependency
source without changing the public production requirements, assertion IDs,
expected observations, weights or wire format. Counts remain 16/12/12/16/18/18/
17/14/19 in catalog order. Each task still maintains exactly one assertions.json.
The legacy R4 remains v2, 38 assertions and 10/90; the other tasks remain v3 and
10/90. No plugin/API/schema breaking change or protocol increment is needed.
The existing v3 gate-order constraint from revision 2 remains in effect.

Fixture edits change per-task adapter identity; Adaptive's csproj/imports also
change adapter identity and its 13 added starter dependencies change task-source
identity. Both feed build identity and must be paired with fresh immutable image
and assembly identities. The rubric hash is deliberately unchanged because the
manifest is unchanged. Old 0.3.1 fixture evidence cannot be reused for edited
adapters, even if the same expected facts happen to match. No old image may be
relabeled to satisfy the new build identity. Unchanged PRF source/adapter inputs
retain their content hashes; a revision number alone is not a content change.
All nine authoring control records remain not-run and prohibit claiming prior
controls as this revision's validation. There is no database migration or evidence
rewrite; retain historical results under their original identities and regenerate
controls on a separately authorized host.

## Adaptive Storage: actual source progress, incomplete closure

[Dependency inventory](../../benchmarks/rimworld-core/private/harbor/adaptive-storage-slot-limit-restore/validation/dependencies.json)
records base/target commits, individual SHA-256 values, common MIT license hash,
compile status and outstanding dependency categories. Thirteen complete files
were fetched independently at both commits; each pair is byte-identical:

- ITransformable, TransformData, RotationAngle;
- StorageCell, ThingGridEventHandler, SpawnMode, LabelFormat;
- Extension, ThingCollection;
- IHasPosition, CellData, CellTable, ValuesByQuality.

Both starter and oracle now contain them, explicit Compile items include them,
and catalog required_files includes them. There are no source transformations,
new packages, DLLs or same-name empty Mod stubs. Support adds namespace imports
only. ThingClass retains its original full base/target bytes, including setter,
PostInitialize, bookkeeping, Notify_SettingsChanged and every production branch.
The pre-existing ThingClass 2.cs copies remain unchanged and excluded.
ThingCollection's real constructor subscribes to StorageSettingsChanged and owns
its cell/free-slot collections; it was not replaced with a fixture implementation.

The original declared references remain Krafs.Rimworld.Ref 1.6.4871,
Lib.Harmony 2.4.2, and net472 reference assemblies 1.0.3, with no direct DLL
Reference items. The unresolved categories are concrete:

- Mod source: Fishery collections/pools/diagnostics, renderer/graphics/PrintData,
  UI/labels/packing/settings and their extension methods. Adding only empty type
  shells would erase behavior, including renderer notifications.
- Private API: ThingClass.CurrentSectionLayer reads MapDrawer.sections, which the
  upstream build publicizes. No publicizer or reflection transformation has been
  selected or validated here.
- Compiler/BCL: upstream net48/preview/PolySharp/Publicizer differs from this
  net472 project; Span/ReadOnlySpan, Array.Fill, ranges, records, compiler metadata
  and JetBrains annotations still need an explicit compatible build closure.
  StorageRenderer additionally uses the preview contextual `field` feature.
- Optional integrations: LWM, PerformanceFish and ToggleableOverlays need reviewed
  optional boundaries. No other Mod or DLC has been made mandatory.
- License: upstream StorageCellRect says it is mostly a copy of Verse.CellRect.
  Its MIT header alone does not establish rights to copied game implementation.
  That file was inspected only in isolated temporary storage and was not copied
  into the repository. StorageCell/ThingCollection still depend on that type. A
  rights-cleared implementation or independently authored equivalent with a
  documented derivation is required; it must retain the real cell semantics.

Thus the task is still blocked by missing source/access/compiler and license
closure, not merely by lack of execution permission. Neither base nor oracle is
claimed compilable. The remaining work cannot be hidden by weakening the task or
bypassing its original production entry point.

## Zombieland: verifier compilation-unit corrections

Verifier.cs now imports HarmonyLib and uses infectedBefore for the membership
snapshot and runOriginalPain for the pain Prefix result. Inspection found no
additional name/scope/reference defect in the verifier or generated 19-entry
partial-class dispatch. This is a source inspection, not a compiler result.
The three retained upstream patch classes and oracle bytes are unchanged.
The local derivation replay independently checked fixed raw input hashes, all
three retained block hashes, output hashes and byte equality with both snapshots.
No full Mod static initializer, network operation, optional Mod or asset loader
has been added.

## Customize Weapon: candidate failure and resource integrity

The control-flow distinction is explicit:

1. RuntimeDefsReady performs a candidate-independent real Scribe disk roundtrip
   using TransportPayload. A changed sentinel/value, absent fresh object, missing
   PostLoadInit, XML/IO/transport error or cleanup failure is fixture-fatal.
2. Every Context requires a holder restoration independently of registering its
   callback; each added AbilityDef requires its own restoration. Fixture setup
   creates the pawn/equipment/holder relationship. Start still goes through
   SetOrUpdateAbilities and equipment AddEquipment/Notify_Equipped. A fixture
   subclass forwards both public notification overrides to the candidate base
   implementation and marks only exceptions crossing that boundary. Equipment
   API errors outside those notifications remain fixture-fatal.
3. With omit-equipped-sync, Start can leave Ability null. The initial cases
   return false/missing facts; dependent state/charge/cooldown cases use
   RequireAbility and throw CandidateFailure. No ability is fabricated and no
   private SyncAbilities call substitutes for the production entry point.
4. Bootstrap records each CandidateFailure as a failed case and continues after
   cleanup. Charge/cooldown restore errors are observations. Null collections
   yield a failing count; unavailable reflection APIs remain fixture failures.
   The prune control now requires the candidate-created ability before pruning,
   avoiding a vacuous pass from an ability that never existed.
5. Post-load cases may return a failing `missing` observation before starting
   Scribe. They have no new scribe-temp obligation. The independent first-gate
   probe already proves transport/cleanup; the terminal gate still requires
   scribe-temp and is not made optional.
6. Each actual Roundtrip requires and registers a new scribe-temp obligation.
   Required/Registered counts are local to the current case; losing one loaded
   holder registration in a two-context case cannot be hidden by the saved
   context's same-name registration. Callback restoration predicates and retained
   boundary snapshots are checked, not just callback list emptiness.
7. Healthy candidate paths still execute fresh provider construction, actual
   PostExposeData and Scribe PostLoadInit, then SetOrUpdateAbilities on the loaded
   equipment. Only candidate calls are wrapped; Scribe infrastructure failures
   remain fatal. Candidate exceptions inside PostExposeData are latched so Verse
   swallowing a payload exception cannot silently turn it into a success.
8. Reloadable lookup/reload operations are scoped candidate calls; absent
   reloadable/ability produces a failed observation rather than fixture null
   dereference. Rand state and stack depth remain independently checked.

Consequently complete=true/passed=false for the candidate mutations is the
**authoring expectation**, not a measured C# outcome. A genuine restoration or
transport failure still makes the run incomplete, even after behavioral failures.

## Nine-task targeted audit

| Task | Candidate/result boundary review |
| --- | --- |
| R4 small bench | Wrap only ConsumeIngredientsOnBench; map/fixture setup remains fatal. |
| PRF cultivator | Existing reflected candidate invocation; setup patches/state mutation precede candidate call; no analogous conditional final obligation found. |
| Adaptive Storage | Missing candidate-produced cell arrays now CandidateFailure; full compile closure still blocked. |
| Combat Readiness | Build fixture map first, then wrap only production Prefix; historical reconstruction/1.6 descendant claims unchanged. |
| Customize Weapon | Ability/result guards, scoped reload/Scribe payload calls and independent transport probe as above. |
| Total Control | Null/wrong-type generated gear becomes CandidateFailure before quality/HP/style dereferences; hitpoint/kind mutations precede generation. |
| Bill Autopilot | Independent transport probe; MemoryNode delegates fields to a fresh real BillMemory.ExposeData within the original XML node; candidate exceptions are latched; null linkedTo is a failing observation. |
| Playwright | Missing candidate state/field/Postfix becomes CandidateFailure, while fixture Scenario/TradeSession reflection remains fatal. |
| Zombieland | Scoped Prefix/Postfix calls; health/membership mutations and required restoration occur before candidate invocation; corrected names/import. |

This audit does not assert that every possible arbitrary candidate mutation will
be classified correctly without C# execution. Private-field fixture assumptions,
Verse exception handling and API compatibility still need the controls below.

## Executable later controls and current verification boundary

[materialize_control.py](../../benchmarks/rimworld-core/private/harbor/customize-weapon-ability-tracker/validation/materialize_control.py)
creates task-owned candidate/adapter source plus a separate private plan from
[mutation-controls.json](../../benchmarks/rimworld-core/private/harbor/customize-weapon-ability-tracker/validation/mutation-controls.json).
It validates input/output hashes and unique anchors, rejects existing outputs,
generates dispatch through the plugin contract and excludes assertions.json from
both candidate and adapter surfaces. It does not compile, launch or score.
Run it in the existing repository Python environment with core/plugin PYTHONPATH:

```sh
python benchmarks/rimworld-core/private/harbor/customize-weapon-ability-tracker/validation/materialize_control.py omit-equipped-sync /absolute/task-owned/state
```

After separate authorization, materialize all nine control IDs, build each
adapter/candidate with fresh per-task immutable evidence, and collect observations
through the unchanged evaluator/supervisor. Never edit a previously verified
image in place or replay another control's result. Verify these exact outcomes:

| Control | Required later outcome |
| --- | --- |
| oracle | All 18 CWF cases pass, including the independent probe and real lifecycle/load cases. |
| omit-equipped-sync | missing-tracker-created and managed-ability-added fail; all 18 records remain; complete=true, passed=false. Later absent-ability cases fail without null-reference fatal. |
| break-holder | holder-update-adds-ability and reload-path-preserved fail; complete=true. |
| omit-state-save | postload-restores-state fails; complete=true. |
| omit-postload-clear | postload-managed-cleared fails; complete=true. |
| break-scribe-transport | First-gate independent value roundtrip fails; incomplete. |
| omit-loaded-holder-restoration | Saved-context callback still exists, loaded-context callback is suppressed; Required count exceeds Registered in the post-load case; incomplete. |
| throw-during-restoration | Restore throws; incomplete. |
| leave-stored-state | Callback runs but captured state remains; real restoration predicate fails; incomplete. |
| extra-rand-push | Unbalanced nesting survives the normal PopState; depth/state check fails; incomplete. |

Then run independent base/nop/oracle for every affected task; reconcile planned
counts only against observed failures without relaxing expected values. Synthetic
Python observation tests exercise only the protocol receiver (including malformed,
missing/duplicate/extra cases and terminal failures). Control materialization tests
exercise file/provenance/isolation behavior only. Neither is C# behavior evidence.

## Checks executed for this revision

The existing Python 3.12 environment ran the safe full suite: 313 passed,
1 deliberately deselected, 1 existing Starlette/httpx deprecation warning.
The excluded test was read before execution and directly calls the real DST
server runner:
`plugins/dst/tests/test_evaluator.py::test_real_headless_server_executes_nonce_bound_assertion_when_available`.
After the final fixture-boundary edits, the RimWorld suite passed again: 202 tests.
Ruff passed for repository Python plus the control materializer; Mypy passed for
87 files when the materializer was checked alongside repository source roots.
Initial Ruff formatting failures were corrected. A standalone Mypy invocation
could not resolve this local plugin as typed; the full source-root invocation
resolved it without ignoring errors or changing package metadata.

Strict JSON (47 files), TOML (10), XML/project (50) and Bash syntax (20 scripts)
checks passed. Ten dispatch files were generated outside the pack. The Zombieland
base/target replay matched all pinned hashes and rejected a modified raw input.
The tracked diff and frozen R4/Isaac checks remained unchanged; diff --check
passed. Devenv and ShellCheck were unavailable and were not installed. Web checks
and wheel building were outside this source/fixture change. All C# reference,
container, real-engine, base/oracle/nop and C# mutation executions remain not-run.
