# Integration verification

The three new tasks were integrated without changing their frozen canonical
bytes or any original task folder/exam. Verification ran on x86-64 Linux in WSL.
The source base is PR #14 head `60cfd75d6eed1909c41da72ccf01dc4a5485cb8f`;
that PR was merged while this follow-up was being prepared.

## Real-engine controls

Six fresh Harbor controls from the repository copies completed with no build,
runtime or harness errors. Baselines reproduce their exact frozen failed-case
sets: 15/46 descriptions, 7/27 block and 5/15 enum assertions pass. References
pass all **88/88** assertions. See [integration-controls.json](integration-controls.json).
The typed/formatted public reconstruction recipe reproduces the identical three
task-image IDs; see [recipe-equivalence.json](recipe-equivalence.json).
These are real loader/game-class controls in Linux containers, not native Windows
engine support evidence.

## Repository checks, including initial failures

- The complete `pytest -q -rs` run collected **1,215** tests: **1,184 passed,
  16 failed, 15 skipped**. It ran from Git source tree
  `8d8e80beee6bc06177f78c31be2a12b6dc4370d9`. Its retained local log has SHA-256
  `18f6eda98be9ace63cac90dc5744f5ae26715057937101673184d7401c9f3eac`.
- Four new integrity tests exposed Git newline normalization of hash-bound
  recipe files. Byte-preserving attributes fixed the export;
  assertions, manifests and expected hashes were not changed. All seven new
  integrity tests then passed against corrected Git export
  `5e3d6f36a36b53aa24e79c1862344696420463c9`.
- Nine authoring failures came from ShellCheck being absent from the full-run
  PATH, including two mock-response exhaustion errors after rejected shell
  checks. The existing isolated ShellCheck 0.11.0 was added to the test PATH.
  One study test required Git repository metadata that a source archive omits;
  the disposable source export was initialized as a local Git repository.
- GMod and Palworld subprocess tests exceeded their unchanged eight-second
  limits. GMod passed unchanged on rerun; Palworld still timed out. Starting
  the Palworld runner with only `--help` took 3.19 seconds with the Python
  distribution on WSL's Windows mount. Moving the byte-identical CPython
  3.12.14 distribution to native Linux storage and recreating the locked
  environment resolved the remaining timeout; no runner, assertion or time
  limit was edited.
- The final targeted run covers all 16 initially failing tests plus the other
  three new integrity tests: **19 passed**. Its retained local log has SHA-256
  `3b9e0b8860021f72cfb4472d5997904a0751e8e9400032931b0e37b32665aa93`. This is a full run followed by corrected targeted
  reruns, not a claim that a single complete run was green.
- Full Ruff checks passed for `src plugins providers tests tools/authoring
  tools/study` and the new native-runtime scripts. Full Mypy checks passed
  across 255 source files, including those scripts.
- Bash syntax and ShellCheck passed for all six new task shell entry points and
  the seven root-required scripts. Only SC2329 is excluded on the three frozen
  `finish` functions invoked through `trap finish EXIT`; their other diagnostics
  remain enabled. The snapshots were not rewritten to silence this false positive.
- `git diff --cached --check` passed. All 1,071 canonical task files matched their
  frozen hashes in the index, an independent Git source export and a fresh
  checkout. The 12 upstream LFS pointer warnings are documented in the
  [validation overview](README.md#frozen-git-attributes); checkout bytes matched.
- Added source and nested build-template archives were recursively inspected
  for unsafe archive members, credential-shaped content and compiled payloads;
  no findings. A private exact-credential scan also passed.

## Skipped and unrun checks

The 15 full-suite skips concern unavailable unrelated runtimes/platforms: two
DST server tests, seven native Windows Balatro tests, one macOS sandbox test,
four GMod native/runtime audit tests and one Palworld server test. No new Slay
the Spire test or required native control was skipped.

Web lint/tests/build and wheel rebuilding were not run: Web and installable
distribution code/data are unchanged. Original task controls remain their
historical records. No native Windows evaluator, managed Hub flow,
or full-suite verification against subsequent unrelated main-branch changes is
claimed by this record.
