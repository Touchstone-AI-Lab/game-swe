# Research-tab task: selection, inputs and acceptance

**Registered in catalog 0.4.0 / authoring revision 3. Real-game acceptance passed
on 2026-10-29.**

The [English exam](../../../../exams/research-organized-tab-state.md) repairs native
tab-visibility state and the persistent research window after tabs are hidden,
restored and re-indexed. It comes from the real single-parent
[ResearchOrganized fix 4941919](https://github.com/Cruesoe/ResearchOrganized/commit/4941919bf33fb84ff280fa64c500c4439118b5e0),
parent `8d978d53095287c85da0bda09b73045ff68d244f`. Difficulty is set to hard and
has not been measured against a model; no comparable-difficulty claim is made.

The task was authored as an unregistered reserve (draft catalogs 0.1.0 and 0.2.0,
2026-10-26). It neither replaces Adaptive Storage nor changes any other task.

## Selection review (2026-10-26)

| Candidate | Decision | Scope and verification cost |
| --- | --- | --- |
| Earlier Playwright permanent-condition filter | Research only | Real MIT/1.6 fix, but simple membership filtering is below the preferred stateful reserve direction. |
| Soil Relocation | Rejected | Only an initial commit was exposed in the audited history; no exact fix pair was established. |
| Playable Recreation match/tutorial/reveal fix | Deferred | Genuine multi-behavior fix; no covering license was established at the selected tree. Requires window, settings and timing fixtures. No source copied into the pack. |
| Playwright origin-settings full build | Rejected after file audit | The MIT root is insufficient to characterize the whole graph: two scenario-part files explicitly say much is copied from game code; one UI file has its own public-domain/CC0 notice. The prototype was removed from the repository. Its successful compilation and Python tests are not acceptance evidence. |
| ResearchOrganized historical layout fix 9a129ba | Rejected at those exact commits | The old graph fix predates the repository's MIT license addition 5736d76. Current repository classification cannot establish the exact earlier trees' license boundary. |
| ResearchOrganized tab-state fix 4941919 | Selected | Both selected trees have byte-identical MIT licenses and explicit 1.6/Harmony metadata. All 13 C# files and archive notice paths were audited before inclusion. Real native state/re-index/window behavior; Core-only fixtures need no map, pawn, save, DLC, screenshot or extra Mod. |

No root-license-only or current-default-branch license assumption is used for the
selected pair. [Provenance](provenance.json) records exact source and archive
hashes, and `audit/` keeps the two trees' unchanged non-code files (definitions,
About metadata, LICENSE, original project). Both complete archives have one LICENSE
and no additional selected-file license or copied-game notice. Only the author's
assembly copyright appears in the selected source's notice scan. The selected code
is retained byte-exact; no game implementation, engine double or production stub is
supplied.

## Inputs

The starter and reference each contain all thirteen complete upstream production
C# files, including startup, settings, Harmony patches, UI and layout. The task
adds the English exam, fixed build projects and locks, the two unchanged original
XML definition files, the real-runtime binding, the digest-pinned role image recipe,
builder/launcher scripts and the protocol v3 private observer. No binaries, art,
game files or upstream tests are included. Original repository-local build settings
are replaced by SDK 8.0.422, C#12, net472 and the common locked reference packages.

The two XML files are declared as `runtime_data_files` in the catalog. Catalog
loading requires them, the runtime builder stages them and binds their bytes into
adapter evidence, and `tests/test.sh` installs them into the candidate Mod. They are
operator inputs, never part of a submission. `input-manifest.json` pins the SHA-256
of every authored input of this task (paths relative to the pack), except the
evidence record `controls.json` and the manifest itself.

The 22 observations have runtime and terminal gates around 20 behaviors: no-game
and lazy-map paths, shrink/restore/re-index of visibility state, native reads after
a game starts with combined tabs, defaults for newly added tabs, repeated passes,
closed-window tab records/current-tab repair, current selection retention, native
view-width recomputation in closed and open windows, open-window re-layout and the
explicit refresh entry point. Native DefMap storage must contain one value per
current tab. The checkpoint restores native definitions (including hidden tabs),
config lists, Mod caches, settings, the persistent window and Current.Game without
calling candidate cleanup. Setup or restoration failure is incomplete; candidate
exceptions or wrong observations are behavioral failures. No private candidate
helper or cache field is a required scoring interface.

## Controls and reference compilation

`reference_compile.py` writes the eight controls (base, oracle, an independently
copied no-op and five negatives) and the build adapter to fresh state outside the
repository. It checks every input against `input-manifest.json` first. With
`--compile` it also restores and builds all sixteen candidate and verifier
assemblies with an existing SDK 8.0.422:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  benchmarks/rimworld-core/private/harbor/research-organized-tab-state/validation/reference_compile.py \
  /absolute/new/research-tab-controls --compile --dotnet /existing/path/to/dotnet
```

A wrong or missing SDK, changed hash, unsafe input, existing output, failed
restore/build or timeout cannot yield compile success, and every run clears prior
compile evidence before probing the SDK. `compile.json` always leaves
`engineValidated` false; the generated adapter has dispatch only and never receives
expected values. Game acquisition, launch, DLLs, logs and output never enter the pack.

Engine controls run through the normal Hub after explicit runtime preparation with
a Steam session that owns RimWorld:

```sh
rhenium runtime prepare rimworld/rimworld-1.6.4871-linux-x64 --account YOUR_ACCOUNT
rhenium run rimworld/core/research-organized-tab-state /absolute/new/research-tab-controls/controls/oracle --profile full
```

Run base, nop and each negative folder the same way. `negative-controls.json` is
the authored plan of which cases each negative must fail.

## Real-game acceptance (2026-10-29)

The first real-game runs found two verifier fixture defects (startup before the
entry UI existed, and a view-width fixture that did not move the window's actual
coordinate). Authoring revision 3 repairs both without changing any case, expected
value, gate, weight, exam, starter or reference; see
[RimWorld support](../../../../../../docs/games/rimworld.md#research-tab-task-catalog-040).
With the repaired verifier:

- three fresh reference runs scored 100 with 22/22 and identical case outcomes;
- base and the independent no-op completed and failed the same 14 target cases;
- each of the five negatives failed at least the cases its plan names;
- an independent alternative fix passed 22/22;
- the E0 study controls behaved as declared.

Run IDs and image identities are recorded in [controls.json](controls.json). The
later upstream background-loading fix stays outside this game-thread task.

## History: draft measurements (2026-10-26, superseded)

Draft 0.1.0 (18 cases) and draft 0.2.0 (22 cases) were measured on macOS arm64
without Docker or a game. Their compile evidence is kept under `history` in
`controls.json`. Both drafts compiled every control with SDK 8.0.422 and zero
warnings. The full Python suite showed seven pre-existing host failures (Git LFS
pointers, case-insensitive filesystem fixtures and absent Docker), none in the
draft. No engine, Linux-image or remote-CI result existed for either draft, and the
draft's native-window and view-width assumptions were first exercised by the
2026-10-29 runs above.
