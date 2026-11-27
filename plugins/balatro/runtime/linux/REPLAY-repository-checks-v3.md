# Repository checks v3 replay

This is repository maintenance. It does not run a model attempt or authorize
authentication, game acquisition, system installation, commits or pushes.
Use a separate Linux/Python 3.12 check environment with the unchanged `uv.lock`
workspace packages and declared dependencies, Bash, Git, ShellCheck 0.9.0, and
Node 22.22.2. The repository's CI normally creates its environment with
`uv sync --locked --all-packages --all-extras`; this batch instead used verified
check-only overlays and existing interpreters, leaving fixed environments intact.

From the repository root, with those check tools on the process-local PATH:

```sh
python -m ruff check src plugins providers tests tools/authoring tools/study
python -m mypy src plugins providers tests tools/authoring/src tools/study/src
python -m pytest -q -ra
npm ci --ignore-scripts --no-audit --no-fund --prefix web
npm run lint --prefix web
npm run test --prefix web -- --maxWorkers=1 --no-file-parallelism
npm run build --prefix web
shellcheck run-benchmark scripts/prepare-exam scripts/score-exam \
  benchmarks/stardew-core/private/harbor/scripts/validate-task.sh \
  providers/steam/helper/build-helper.sh \
  providers/steam/src/rhenium_steam/interactive-launch-v1.sh
git diff --check
```

The current `.github/workflows/ci.yml` supplies the wider shell path groups used
in this batch: 349 Bash syntax inputs and 328 ShellCheck inputs. Preserve its
existing Slay the Spire exclusion pair; do not introduce new suppressions.

On the existing Windows Python 3.12 check interpreter, run:

```text
python -m pytest -q -ra plugins/balatro/tests/test_balatro_native.py plugins/balatro/tests/test_balatro_readiness.py
```

The six-file integrity gate is part of the complete pytest suite. Git byte
verification must additionally compare filtered/index blobs against working bytes
for every proposed path, including untracked additions. This batch uses a private
audit index; it does not stage the operator's branch. Preserve `web/dist/.keep`
when checking tracked inputs after Vite rebuilds its output directory.

Exact local invocations, minimized environment construction, source copies and
failure receipts are retained in the operator's ignored
`.test-state/repository-checks-v3/` directory. `check-complete.py` records the
Ruff/Mypy commands, `check-native-v2.py` the final complete pytest run,
`frontend-checks-v2.py` frontend lint/tests, and `frontend-checks-v3.py` the final
build. `shell-checks.py`, `windows-helper-checks.py`, `observer-checks.py` and the
final private Git audit record the additional coverage. These private receipts
are not included in participant packages or claimed to be remote CI artifacts.

See [the report](REPOSITORY-CHECKS-REPORT-v3.md) for conditional skips, tool versions,
warnings and retained v2 engine evidence. A new source version needs its own
receipts; do not relabel old engine results or overwrite these records.
