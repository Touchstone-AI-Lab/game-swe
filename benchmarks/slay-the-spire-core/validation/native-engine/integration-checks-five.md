# Five-task integration verification

The two additions extend PR #16 to five native tasks without changing any frozen
task bytes. The pack also retains the three original standalone ModTheSpire tasks.
The integration base was `dc1b12ca4d742789bff80f1cf17756fa21fe7107`.

## Real-engine reproduction

All ten fresh Harbor nop/oracle controls completed with zero build, native-process
or harness errors. Nop results reproduce their exact frozen failure sets:
15/46 descriptions, 7/27 block, 5/15 enum, 19/43 icons, and 19/38 Stasis.
The five references pass **169/169** assertions. See
[integration-controls-five.json](integration-controls-five.json).

The actual repository preparation entry point rebuilt all five agent images and
produced execution files byte-identical to these control inputs; the explicit
Downfall runtime map was exercised. See
[recipe-equivalence-five.json](recipe-equivalence-five.json). The first recipe
attempt failed while copying from WSL's Windows mount with `Errno 12`; it did not
reach image preparation. The successful repeat used the exact Git source export
on native Linux storage, without changing code, assertions or time limits.

The public Downfall resource recipe was tested from a fresh pinned Git fetch;
all 8,104 resource hashes and the final archive hash reproduced. Its typed resource
and foundation helpers were exercised in the source-reproduction build. The
495 MB resource archive, compiled SDK and licensed game remain outside Git.

These are real loader/game controls in Linux containers on WSL. They do not establish
a native Windows evaluator or managed Hub integration.

## Repository checks

Checks ran from Git export `d9c193b783a2f9030e1e9a786e3d15e28ac04fa7` on native Linux storage with the
locked Python 3.12.14 environment. Subsequent integration changes are documentation
and compact receipts; tested Python and frozen tasks are unchanged.

- Full pytest: **1207 passed, 15 skipped, zero failures**
  from 1222 tests. Log SHA-256:
  `5411c4cd942b86fa49395b418c9a06256d20c69a69408047e3d1d2a381d6d17f`.
- All 14 targeted task-integrity and preparation tests pass, including explicit
  runtime-map rejection/forwarding.
- Ruff passes across `src plugins providers tests tools/authoring tools/study`
  and the native-runtime helpers. Mypy passes across `src plugins providers tests`
  and those helpers (211 source files).
- Bash syntax and ShellCheck pass for all 17 applicable entry points. Only SC2329
  is excluded for five frozen `finish` functions invoked indirectly by EXIT traps;
  every other diagnostic remains enabled. Canonical scripts are unchanged.
- Web lint, its one Vitest test, and the production build pass on Windows with
  Node v25.2.1 in a disposable copy using the unchanged dependency
  lock. Lint emits existing React warnings. npm also warns that this Node version
  is outside jsdom's declared engine range; the commands nevertheless complete
  successfully. This is a tested local execution, not a claim of engine-range support.
- All 4,850 canonical file hashes match the Git index, an independent source export,
  and a fresh checkout without local attributes overrides. Git LFS warns about 24
  ordinary upstream PNGs; every checked-out byte still matches. The public source
  export needs no LFS download.
- Source archives and nested build templates were recursively scanned: 5,192
  entries, no unsafe members, compiled payloads or credential-shaped content.
  A separate exact-credential scan also passed before staging.

## Skipped and unrun checks

The 15 skips concern two unavailable DST server tests, seven native Windows Balatro
tests, one macOS sandbox test, four GMod runtime/audit tests, and one Palworld server
test. No Slay the Spire integrity test or required native control was skipped.
The suite emits one existing Starlette/httpx deprecation warning.

Wheel rebuilding was not run because installable distribution code/data are
unchanged. Original standalone task controls retain
their historical records. The earlier three-task integration history, including
its failures and corrected reruns, remains in [integration-checks.md](integration-checks.md).
