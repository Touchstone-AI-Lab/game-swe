# Native task controls

Catalog 1.4.0 supersedes socket r2 with r3. The records below retain the original
r2 source and controls; they are not r3 results. The r3 authoring
review is in `downfall-socket-flow-r3/`. The
[final Lab receipt](lab-steam-runtime-controls-r3.json) records twelve complete
Hub NOP/gold runs (199/199 gold assertions) and three socket author variants.

Catalog 1.5.0 likewise supersedes the enum JVM probe r2 with r3, which runs the
same fifteen fixtures inside real game launches. The r3 authoring review and
compact Hub control receipt are in `mts-enum-identity-r3/`. The `mts-enum-identity-r2/`
records below describe the JVM probe only and are not r3 results.

Catalog 1.6.0 replaces the loader-only `mts-load-order-regressions` with
`mts-load-order-regressions-r2`, which runs r1's unchanged JUnit suite inside the real
game; its review and Hub receipt are in `mts-load-order-regressions-r2/`. Catalog 1.7.0
does the same for `mts-mod-identity-regressions` (`mts-mod-identity-regressions-r2/`), and
[lab-steam-runtime-controls-catalog-1.7.0.json](lab-steam-runtime-controls-catalog-1.7.0.json)
replays NOP and gold of all nine admitted tasks. Plugin 0.7.0 disables full results for
loader-only paths; only the nine game-launching tasks can produce complete game-backed
results.

Catalog 1.8.0 retires `mts-loader-internals-regressions` (SG-131) without a replacement.
Its starter's injected `PostfixPatchInfo` defect makes the loader treat a void method's first
postfix parameter as a result. ModTheSpire's own core postfix `ModsScreenUpdateRender$Render`,
on the void `MainMenuScreen.render`, then fails to compile, patching aborts and the real game
never launches for an unrepaired submission. No assertion can be observed in the game for
the NOP, so the required NOP gate is impossible there; the reference passed 16/16 in a Lab
prototype of the in-game harness. Its exam, source, verifier and study controls are
preserved unchanged.

This directory records the seven additional frozen tasks. Their complete source
manifests and compact author-control receipts are committed. Raw game logs and
prepared licensed images remain local, identified by hashes where applicable.

| Task | Nop | Reference | Independent repair |
|---|---:|---:|---:|
| Descriptions | 15/46 | 46/46 | 46/46 |
| Block settlement | 7/27 | 27/27 | 27/27 |
| Enum consistency (r2 JVM probe, retired) | 5/15 | 15/15 | 15/15 |
| Icon layout | 19/43 | 43/43 | 43/43 |
| Stasis lifecycle | 19/38 | 38/38 | 38/38 |
| Event transitions | 13/32 | 32/32 | 32/32 |
| Campfire selection | 6/13 | 13/13 | 13/13 |

## Author controls and reproducibility

Each task directory contains:

- `frozen-manifest.json`: hashes of every frozen canonical file, including the
  private build template and historical task image identities;
- `author-controls.json`: full baseline, reference, alternate repair and
  isolation/omission outcome sets, plus original formal nop/oracle outcomes;
- `author-repairs/`: the source inputs bound by the audited author build receipts.

Descriptions include both independent clause isolations and omission controls;
the block and enum matrices isolate each repair group. All full references and
independently different full repairs pass. Assertions grade behavior and preserve
positive controls. Enum fixtures are compiled against the original public SDK,
so breaking compatibility with existing compiled mods is a real contract failure.

[integration-controls-five.json](integration-controls-five.json) records ten fresh
nop/oracle runs from frozen sources on a separately reconstructed local runtime.
The repository preparation entry point reproduces exactly the same execution
files and image identities, as recorded in
[recipe-equivalence-five.json](recipe-equivalence-five.json). The replay requires
exact baseline failed-case sets, not merely zero reward, and all reference cases
passing.
The new [event](basemod-phase-transitions-r1/fairness-review.md) and
[campfire selection](downfall-socket-flow-r2/fairness-review.md) author reviews explain fixture
validity and the independently different repairs; their hashes are bound by each
task's author-controls receipt. The frozen task metadata retains its original
difficulty value; the catalog difficulty is set in the pack catalog without
rewriting frozen task bytes. The two latest tasks additionally
have four fresh repository-prepared nop/oracle controls in
[integration-controls-two-more.json](integration-controls-two-more.json).
[recipe-equivalence-seven.json](recipe-equivalence-seven.json) verifies the current
seven-task preparation entry point; the earlier five receipts remain historical.
Use the [runtime instructions](../../private/native-runtime/README.md) to reproduce.

Historical native-runtime validation used Linux containers on WSL and software
OpenGL. It does not establish a native Windows evaluator or a managed Hub flow.
The task-source and contract separation is reviewed in [independence.md](independence.md).

## Frozen Git attributes

The canonical snapshots retain upstream `.gitattributes` files. The merged base
stores 24 StSLib PNGs as Git LFS pointers. This change preserves those exact Git
objects and uses their SHA-256-verified image payloads for execution. Earlier
five-task receipts describe their historical pre-merge checkout; the merged tree
requires LFS materialization before integrity tests or runtime preparation.
The current fresh checkout uses the existing local LFS object cache, without
attribute overrides. Its 8,938 native task files and the LFS-materialized Git
export match the frozen manifests. A clone without those objects must fetch them
with Git LFS. Ordinary text normalization or unresolved pointers fail the manifest
checks; no frozen manifest was changed to accept them.

ShellCheck 0.11.0 reports SC2329 on the frozen verifier `finish` functions,
which are invoked indirectly by `trap finish EXIT`. That specific false positive
is excluded for those scripts; all other shell diagnostics remain enabled.

See [integration-checks-two-more.md](integration-checks-two-more.md) for the current
seven-task integration checks. See [integration-checks-five.md](integration-checks-five.md) for the final five-task
repository checks and skipped or unrun checks. The earlier three-task integration,
including its initial failures and corrective reruns, remains recorded in
[integration-checks.md](integration-checks.md).
