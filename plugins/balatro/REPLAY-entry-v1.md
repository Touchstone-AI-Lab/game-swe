# Replay the entry-only verification

These commands are repository-maintenance checks. They do not start an exam model
or a native game. A `full` run currently returns exit 1, `complete=false`,
`passed=false`, category `incomplete`, reason `runtime_action_required`. This is
expected fail-closed behavior, not successful game scoring.

Use the separate Python 3.12 environment at `.venv-platform`. Fixed PoC Python
3.13 and game dependencies must remain unchanged. Development dependency versions
came from the existing `uv.lock`; the sole lock addition is the new local plugin.
Build tools are recorded separately in the local installation evidence.

From the staging repository root:

```powershell
.\.venv-platform\Scripts\python.exe -m ruff check src plugins providers tests
$env:MYPYPATH = (Join-Path (Get-Location) 'src')
.\.venv-platform\Scripts\python.exe -m mypy plugins/balatro
.\.venv-platform\Scripts\python.exe -m pytest plugins/balatro/tests plugins/contract/tests tests/test_plugin_architecture.py tests/test_evaluation_host.py tests/test_cli.py tests/test_config.py tests/test_database.py -q
```

For a fresh entry demonstration, choose fresh state and attempt directories. The
attempt must be outside this repository and every benchmark pack. Do not reuse
or overwrite the recorded evidence directories.

```powershell
$repo = (Get-Location).Path
$runSuffix = [guid]::NewGuid().ToString('N')
$runState = Join-Path $repo ('.test-state/balatro-replay-' + $runSuffix)
$attempt = Join-Path (Split-Path $repo -Parent) ('balatro-attempt-' + $runSuffix)
$env:RHENIUM_ROOT = $repo
$env:RHENIUM_STATE_DIR = Join-Path $runState 'hub'
$env:RHENIUM_CACHE_DIR = Join-Path $runState 'cache'
$env:RHENIUM_DATABASE_URL = 'sqlite:///' + (Join-Path $env:RHENIUM_STATE_DIR 'state.sqlite')
$env:RHENIUM_BENCHMARK_PATH = Join-Path $repo 'benchmarks/balatro'
.\.venv-platform\Scripts\python.exe -I -B -m rhenium.cli tasks
.\.venv-platform\Scripts\python.exe -I -B -m rhenium.cli prepare-attempt balatro/core/growth-v2 $attempt --score-command (Join-Path $repo 'scripts/score-exam.ps1') --mode strict
.\.venv-platform\Scripts\python.exe -I -B -m rhenium.cli run-attempt $attempt --profile full
```

The recorded CLI check additionally used an explicit minimal child environment
with isolated temporary/profile/appdata directories. It printed only environment
key names. The anonymous result includes the opaque run ID and submission hash;
it contains no task key, pack path, assertion expectations or log text.

Full repository checks remain mandatory. Their current Windows failures and
unavailable tooling are listed in `ENTRY-REPORT-v1.md`; the targeted command above
does not replace them. No native or disposable-host replay is offered before the
runtime decision and implementation are complete.
