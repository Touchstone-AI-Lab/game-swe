# Repository checks v3 — Linux branch maintenance

Date: 2026-11-01. Branch: `feat/balatro-linux-runtime`.
Base HEAD: `e4f8326e388cae4fc4ee5066eff792a6ea7a3a72`.

The full Ruff, Mypy and pytest gates now pass in the prepared Linux check
environment. Frontend and shell checks also pass. This is local submission-review
evidence, not a remote CI pass, release approval or untrusted-host validation.
No work-branch staging, commit, push or PR was performed.

## Changes and scope

- Applied the explicitly approved [six-file exception](CHECK-SCOPE-CHANGE-REQUEST-v1.md).
  Ruff ignores only the recorded existing rule codes at those exact paths. Mypy
  excludes their two closed snapshot roots and skips the frozen legacy imports.
  Maintained code retains its original strict checks.
- Added a six-file byte/provenance/closure/configuration gate, including negative
  controls for changed bytes, extra modules, repinning and widened exceptions.
  It validates against the original asset/probe authorities, not newly accepted
  hashes. None of the six files was edited.
- Corrected maintained test-double annotations and monkeypatch use in the Steam
  tests. Added a typed-catalog guard to the old v1 maintenance control launcher.
  No candidate, fixture assertion, production evaluator, RPC or acquisition
  implementation changed during this maintenance batch.
- Added exact-path Git attributes for 23 existing CRLF resources/records. Git
  otherwise changed, for example, the saved probe's blob from
  `8c449ad9e5b1d075f94532547e203226e3029953` to
  `753ef33e4643e366f086db22c3dfc9d4b37323b7` during filtering. The attributes preserve
  the recorded bytes and treat CR as a line terminator, retaining the ordinary
  blank/tab checks. Removed one extra EOF blank line from the current Steam
  operator guide. Historical evidence files and hashes were not rewritten.

## Completed checks

| Check | Result |
| --- | --- |
| Ruff, including authoring/study tools | Passed |
| Mypy, including authoring/study tools | Passed: 386 source files |
| Complete configured Linux pytest suite | 2300 passed, 22 skipped, 0 failures/errors |
| Windows Job/lock/readiness helper suite | 14 passed; covers the 7 Windows-only Linux skips |
| Frozen-scope and directly related development tests | 34 passed |
| Frontend lint | Passed: 0 errors, 8 existing warnings |
| Frontend tests | 1 passed, 0 failed; one worker, file parallelism disabled |
| Frontend production build | Passed; source/lock bytes preserved |
| Bash syntax | 349 scripts passed |
| ShellCheck | 328 scripts passed |
| Windows wrapper syntax | 2 scripts passed |
| Steam observer JavaScript unit programs | Both passed with fake bindings, no client/network |
| Protection and original dependency audit | Passed: 16 controllers, 350 private assets, 6 dependency groups |

Shell coverage includes the previously absent Stardew script, the changed
Steam launcher, and the current CI shell groups. The Slay the Spire group retains
only CI's existing SC2317/SC2329 exclusions; no new shell suppression was added.
Ruff/Mypy use the approved six-copy scope, not a claim that frozen historical
snapshots were reformatted or newly type-corrected.

Git scope/blob/whitespace checks use an independent audit index. Its exact path
set and blob bytes are compared with the worktree; the work branch's index and
HEAD remain unchanged. See the versioned validation and source manifest for the
final audit and evidence identities.

## Environment corrections and retained failures

The former missing repository files came from sparse checkout. Existing HEAD
content was materialized without editing tracked benchmark files. Full Python
checks require all workspace source roots, plugin distribution metadata, and the
lock-declared tree-sitter, tree-sitter-lua and Lupa wheels. These were provided in
separate check-only directories; existing Python environments and locks were not
updated. Plugin metadata was extracted from actual locally built workspace wheels.

A byte-verified copy of 55,347 repository input files was used on WSL's local
filesystem. The first Windows-mount run was interrupted during directory traversal
after 147 passes and remains incomplete. The first complete local-copy run had
2188 passes, 108 failures and 26 skips: missing Git metadata, Lupa, workspace
entry points and ShellCheck availability explained those failures. After correcting
the check environment, the same test code completed with the result above.

The approved Node 22.19.0 tool was below the unchanged jsdom 30.0.1 requirement.
The separately approved [Node adjustment](CHECK-NODE-CHANGE-REQUEST-v1.md) added
22.22.2 without replacing the old tool. Node archives and the isolated ShellCheck
0.9.0-1 package were hash-verified. Frontend dependency installation scripts stayed
disabled; no system installer, global PATH change or new container was used.

Operator-control failures are also retained: two premature frontend launches ran
no checks; a post-build audit initially treated Vite's removal of the output
`.keep` marker as source loss. Readiness gating and explicit preservation of that
tracked output marker corrected these checks without changing frontend source or
test assertions. An initial Git scan on the Windows mount was interrupted for
filesystem overhead; native Windows enumeration and a private Linux audit index
replaced it. The first private-index whitespace audit identified the operator
guide's extra EOF blank line; that failure remains recorded separately.

## Preserved engine evidence and remaining limits

The [v2 engine report](LINUX-RUNTIME-REPORT-v2.md), manifests, private receipts,
source capsule and original halts retain their own identities. The packaged
Balatro/Steam production sources remain byte-identical to that revision. Its
20 controls / 56 normal game processes / 912 required outcomes, three initialized
save/load probes, and wheel/artifact checks are retained evidence, not new v3 runs.
No game was launched in this batch. The old v1 launcher guard is a maintenance
type check; it is not a new engine or lifecycle capability claim.

The 22 Linux skips comprise 7 Windows-specific tests (separately passed above),
8 unavailable/opt-in other-game engine checks, 1 actual-macOS check, and 6 checks
requiring javac 21+. The latter 15 remain unexecuted here. No unrelated engine or
Java toolchain was acquired to remove those skips.

Nix/devenv and the stock shell scorer's full engine path remain unrun. The shell
scorer genuinely requires Nix/devenv; syntax and unit tests do not replace that
end-to-end path. Remote CI, a fresh core-only installation, unrelated CI compiler
jobs and full engine evaluation from installed wheels were not run in this batch.
The existing affected-wheel checks are retained with matching packaged-source
bytes. No core runtime or packaging implementation was changed here.

The eight frontend lint warnings are retained. No lint severity, test assertion,
timeout or benchmark pass criterion was relaxed to obtain the passing results.
This branch remains Experimental, source-reviewed honest execution only. Other
hosts, hostile-code isolation, release/version approval and model calibration
remain outside this result.

## Records

- [Machine-readable checks](validation-repository-checks-v3.json)
- [Source and evidence identities](runtime-manifest-repository-checks-v3.json)
- [Replay commands](REPLAY-repository-checks-v3.md)

Raw logs, JUnit, dependency receipts, source copies, built frontend outputs and
private audit indexes remain under ignored operator state. They are not source
or public task-package assets.
