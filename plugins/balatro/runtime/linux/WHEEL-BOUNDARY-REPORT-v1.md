# Balatro wheel boundary repair v1

Repository maintenance recorded 2026-11-01 after
`afc81875f124567fd4f8dd64ccaaa2fd926abb01`.
This repair changes the CI resource allowlist and its regression tests, not the
plugin payload, runtime identity, task contracts, dependencies or scoring behavior.

## Failure and repair

The [PR #40 package job](https://github.com/Touchstone-AI-Lab/SWE-Game/actions/runs/41226683164/job/124612186072)
built the Balatro wheel successfully but rejected its 13 nested Linux resources.
The gate collected only top-level Python modules. A fresh local build reproduced
the original complete gate's assertion and exact 13-file difference before edits.

The workflow now names those resources individually. It retains exact archive
membership, duplicate rejection, byte equality with reviewed source, local-path
rejection, entry point, name/version/dependency metadata and core-wheel isolation
checks. It does not recursively allow arbitrary nested content.

All paths below are relative to `rhenium_balatro/`:

| Resources | Purpose and source |
| --- | --- |
| `linux_assets/dependencies-v1.json` | Existing fixed-download URLs, checksums and file inventories; no downloaded component or game payload. |
| `linux_assets/legacy/poc/{checks,evaluate,rpc}.py` | Three byte-frozen, self-authored compatibility modules for verdicts, sessions and RPC. The existing six-file integrity gate remains unchanged. |
| `linux_assets/mods/poc_control/{control.lua,poc_control.json}` | Existing self-authored isolated-run preparation and runtime observation module. |
| `linux_assets/mods/poc_guard/{guard.lua,lovely.toml}` | Existing self-authored path/isolation guard and loader configuration. |
| `linux_transport_v1/{LICENSE-BalatroBot,send_raw.lua}` | Previously approved versioned transport replacement and its MIT attribution, retained together. |
| `linux_window_v2/{window.json,window.lua}` | Existing self-authored owned-window profile. |
| `linux_assets/.gitattributes` | Existing byte-preservation rule, already included in the recipe's complete resource identity. |

Although `.gitattributes` is not executed by the game, removing it from the wheel
would change the resource closure consumed by `linux_runtime.recipe_identity()`
and `linux_managed_v2.recipe()`. It remains byte-identical. Neither old recipe
hashes nor artifact/smoke identities are rewritten to accommodate packaging.

## Validation

- Original CI gate: expected failure reproduced against newly built artifacts.
- Repaired complete gate: passed against those same artifacts, including the
  core-wheel exclusion check; no package source was changed between checks.
- New regression tests: 44 passed. These execute the actual workflow's Python
  gate, not a second implementation. Synthetic archives cover all 13 resources
  missing/corrupted, added files even when present in source, local paths,
  incorrect entry points/metadata, core contamination and duplicate members.
- Local packaging: all 18 wheels and 17 source distributions built; the unchanged
  downstream GMod gate and extension/core-source archive inspection passed.
  All 17 source distributions also rebuilt into wheels with exactly the same
  archive members and bytes as the direct builds, covering uv's source-to-wheel
  build sequence without acquiring another build tool.
  Builds used the existing Python 3.12 Hatchling backend, without downloads or
  dependency changes. This is not a claim of rerunning the remote Ubuntu/uv job.
- Full Ruff passed; full Mypy passed for 387 source files.
- Final complete pytest: 2,344 passed, 22 skipped, zero failures/errors, in
  647 seconds. The skips comprise eight unavailable/opt-in real-engine checks,
  seven Windows helper checks, one actual-macOS check and six Java 21 checks.
  Two existing library deprecation warnings and the 120-second diagnostic stack
  from the 133-second Palworld packaging test are retained; that test completed
  successfully without changing its timeout. All 55,353 snapshot source files
  remained byte-identical after the suite.

The build workspace reused all 11 hash-verified production Web output files from
the earlier local frontend validation. Frontend lint/test/build and shell suites
were not rerun for this CI-only repair. Installed-wheel engine execution,
Nix/devenv's complete scoring path, remote CI on this patch and merge-base
integration with newer `main` are not claimed. No game or model experiment ran.

Local setup failures remain recorded separately from the wheel defect. A slow
Windows mount-based run was interrupted. The first fresh Linux snapshot lacked
Git metadata; an isolated Git initialization let all 59 affected repository and
catalog tests pass unchanged. A subsequent complete suite exposed 13 failures
from the omitted ShellCheck path and one requiring a valid Git HEAD. Restoring
the already approved, hash-verified check tools to the process-local PATH and
referencing the existing published commit through read-only Git object access
resolved those prerequisites; all tool tests passed, with six Java 21 skips.
No test assertion was changed for these failures. The working branch, its index
and remote were not changed, and no new commit was created for the test copy.
The initial new-test line-length failure and formatting-only correction also
remain in the receipts.

## Replay and evidence

From a correctly prepared repository check environment, with a valid Git HEAD
and the approved ShellCheck available on the check process's PATH:

```sh
python -m pytest -q plugins/balatro/tests/test_wheel_boundary.py
python -m ruff check src plugins providers tests tools/authoring tools/study
python -m mypy src plugins providers tests tools/authoring/src tools/study/src
python -m pytest -q -ra
```

For built-wheel validation, run the complete `package-metadata` job in
`.github/workflows/ci.yml`, including its frontend build, package builds and all
three archive checks. The new unit test is not a substitute for building wheels.

New private receipts are under `.test-state/wheel-boundary-v1/`: original/fixed
gate sources and logs, build hashes, subsequent gate results, input manifest,
full check logs, and the final validation/submission manifests. They are excluded
from Git and participant packages. Historical v1/v2/v3 records remain unchanged.
These are local validation results recorded before delivery. Remote CI must be
checked after any separately authorized commit/push to PR #40.
