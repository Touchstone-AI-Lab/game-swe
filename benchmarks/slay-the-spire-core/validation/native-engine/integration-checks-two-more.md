# Two additional native tasks: integration verification

The pack is version 1.3.0 with ten tasks: three original standalone tasks and
seven native tasks. This change adds BaseMod event transitions and Downfall
campfire selection on base `c944028fd2450b6daf4bbfa888cb6a0295867170`.
The eight prior frozen task packages and public reports are unchanged.

## Real-game controls

The repository preparation entry point rebuilt all seven task images. The
five older execution copies and their image identities exactly match the
previously completed source-reproduction controls. The two new execution copies
were exercised by four fresh Harbor runs: nop 13/32 and 6/13, oracle 32/32 and
13/13, with exact baseline failure sets and zero build, game or harness errors.
See [recipe-equivalence-seven.json](recipe-equivalence-seven.json) and
[integration-controls-two-more.json](integration-controls-two-more.json).
The ten old control runs remain historical; fourteen fresh runs are not claimed.

Each addition has an unmodified upstream baseline, a complete reference repair,
a structurally different complete repair and exact isolated-repair controls.
The compilation, expiration, modal, ghost-wheel, hit-resolution, card-transit,
stun, power-dispatch, expression-types, Gremlin-event, VFX-clock and
extra-effect-lifetime candidates remain retired. Earlier transfer/persistence and
reconstruction candidates remain excluded.

The native verifiers execute the real game and public mod APIs in offline Linux
containers on WSL with Xvfb/software OpenGL. They preserve the existing manual
licensed-game workflow. The Hub lists native tasks but does not evaluate them;
its native-task verdict remains incomplete. This does not establish a native
Windows evaluator or a managed native Hub runtime.

## Repository verification

Checks ran from Git export `0b226443661dcc5f16c32c846ae66980925fa2ac` with the locked Python 3.12.14
environment on native Linux storage. Later changes are documentation and compact
verification receipts, plus enabling LFS in the two CI checkouts that run frozen
asset integrity tests; tested Python, recipe code and frozen tasks are unchanged.

- Full pytest: **1537 passed, 15 skipped**, zero
  failures, out of 1552 tests. The 19 targeted task-integrity,
  runtime-preparation and catalog tests pass.
- Ruff passes across core, plugins, providers, tests, authoring/study tools and
  native-runtime helpers. Mypy passes across core, plugins, providers, tests and
  native-runtime helpers.
- Bash syntax and ShellCheck pass on all 23 applicable scripts. Only SC2329 is
  excluded for frozen `finish` functions invoked through EXIT traps; all other
  diagnostics remain enabled.
- Web lint, its Vitest test and production build pass using unchanged Web source
  and lock bytes in a disposable Windows copy on Node v25.2.1.
  Existing React lint warnings remain. npm warns that this Node version is outside
  jsdom's declared range; this records the actual successful local run without
  claiming engine-range compatibility.
- All **8,938** native canonical files match their frozen manifests,
  the LFS-resolved Git index, a Git source export and a fresh checkout without
  local attribute overrides. The merged base stores 24 StSLib images as LFS
  pointers; their Git objects are unchanged and their verified payloads come from
  the existing local LFS cache. A clone without those objects must fetch them.
- A separate empty-cache fetch from origin/main verifies all 12 unique LFS objects
  for those 24 paths. CI now enables LFS for the two jobs running asset integrity
  tests. This corrects transport setup without rewriting frozen task bytes.
- Clean core and Slay the Spire plugin wheel builds pass. Inspection verifies
  Python source, entry points, production Web files, the updated README metadata,
  and exclusion of private benchmark and licensed runtime payloads.
- Source and nested build archives pass recursive member/content scans; a separate
  exact-credential scan passes before staging. No game, compiled SDK, prepared
  licensed image, credential or model trajectory is included.

## Skipped and unrun checks

The 15 skips concern two DST server tests, seven native Windows Balatro tests,
one macOS sandbox test, four GMod runtime/audit tests and one Palworld server test.
No Slay the Spire integrity test or required native control is skipped. The suite
retains the existing Starlette/httpx deprecation warning.

The original standalone tasks retain their historical controls.
Hosted CI is reported separately from these local checks in the pull request.
See [repository-checks-two-more.json](repository-checks-two-more.json) for commands
and hashes, and the prior [five-task report](integration-checks-five.md) for
unchanged historical reconstruction evidence.
