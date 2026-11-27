# rhenium-rimworld

Independent Rhenium 0.6 plugin for RimWorld benchmarks. It owns the RimWorld
catalog model, public attempt materialization, fail-closed evaluator and licensed
Steam runtime builder. The distribution contains no game files, Mod binaries,
Steam state or Workshop cache.

The first in-development pack is `rimworld/core` 0.5.0 with ten source-authored
tasks. Its reduced `core` profile
performs only a source-shape diagnostic and is always incomplete. A `full` result
can pass only after every private assertion runs inside the prepared, pinned real
game.

Runtime preparation creates separate immutable builder and evaluator image roles.
The builder receives only a task-scoped, hashed C# snapshot and uses packages
restored into its fixed toolchain during explicit preparation; evaluation uses
`--no-restore`. The evaluator receives only the re-read candidate and adapter
assemblies. Neither role receives a Docker socket, Steam session, user directory,
reference solution, expected-result file, or final verdict writer.

Both roles run without networking as a non-root user, with a read-only root
filesystem, dropped capabilities, `no-new-privileges`, resource limits, bounded
local Docker logs, and minimal tmpfs mounts. A plugin-owned external supervisor
validates a per-evaluation nonce, canonical task key, exact case set, process and
terminal evidence, and hashes for the catalog, rubric, source snapshot,
assemblies, runtime artifact, role image IDs, and staged build inputs. Detailed
evidence remains below the owner-only Rhenium state directory. A complete operator
result names each case with a pass/fail boolean (`runtime.caseOutcomes`);
anonymous results drop it and use generic failure categories.

The original R⁴ task keeps private protocol v2 and its exact 38-case contract.
Protocol v3 gives every additional task its own declared assertion count without
reusing the v2 evidence identity. Each task supplies one pack-owned
`tests/assertions.json`; runtime preparation validates it against catalog metadata
and generates only observation dispatch. The manifest and expected results are
not copied into either runtime image or mounted into the candidate process.

Starter root, package ID, assembly name, Mod metadata path, assertion count,
rubric hash, task-source hash, adapter evidence, and immutable builder/evaluator
image identities are task-scoped. Old artifacts or evidence whose task, protocol,
rubric, adapter, or source identity is stale are rejected.

This is defense in depth, not isolation from an arbitrary malicious .NET program.
The candidate and observation adapter still execute in the same RimWorld CLR, so
the candidate may interfere with adapter code or observations. Nonces, an external
supervisor, assembly hashing, and source-string screening do not prove resistance
to that threat. Such a claim requires a separately reviewed process/isolation
design.

Since catalog 0.3.2, loading rejects v3 manifests whose two gates do not bracket all behavior
fixtures. The data contract retains protocol v3 and 10/90 weights; the legacy
v2 manifest remains unchanged. See the authoring revision 3 migration review
for stale-artifact invalidation and unrun C# validation.

Catalog 0.3.4 repairs Adaptive Storage's C#12 build compatibility and uses the
public `CellRect.Cells` enumerable in its thin rectangle adapter. Its fixed-SDK
compile commands build fresh base, reference and no-op candidates and verifiers with
SDK 8.0.422. Local macOS reference compilation passed; Linux image construction and
all real-engine controls for these inputs remain unrun. See
[revision 5](../../docs/games/rimworld-authoring-revision-5.md).

## Task-owned runtime definitions

A catalog task may declare `runtime_data_files`: up to 64 unique, normalized XML
paths below `tests/ModMetadata/<starter_root>/Defs/`. The field defaults to an
empty list, which every task except the research-tab task uses.

- Catalog loading fails when a declared file is missing, outside that directory,
  not `.xml`, or listed twice.
- The runtime builder copies each declared file into the task's build context
  next to the Mod metadata. Nothing else under `Defs/` is staged, so an
  undeclared file never reaches the evaluator image.
- Adapter evidence hashes every declared file. Changing one invalidates the
  prepared role images, and `rhenium runtime prepare` rebuilds them.
- The task's own `tests/test.sh` installs the staged definitions into the
  candidate Mod (`Mods/Candidate/Defs`) before the game starts.

These files are fixed operator inputs, such as a source Mod's unchanged
definition XML. They are not part of the candidate submission and never reach
an attempt workspace.

Catalog 0.4.0 registers the research-tab task, **Keep research-tab state
consistent after re-layout**, from Research: Organized. It is the first task to
declare runtime definitions: the Mod's two unchanged `Defs` files. See
[RimWorld support](../../docs/games/rimworld.md#research-tab-task-catalog-040).
