# Native maintenance replay v1

This is the scoped approved honest maintenance workflow. It executes only reviewed
controls from the private pack. It does not prepare a licensed runtime or provide
an untrusted/disposable host. Original PoC Python, source, pins and protected data
must match; a mismatch is a stop, never permission to repin.

Use the separate platform Python 3.12 environment with the built Balatro 0.2.1
wheel installed. The bound external PoC controller remains Python 3.13. Choose
fresh state/evidence/attempt paths for every batch; never overwrite old evidence.
From the staging repository root, for example:

```powershell
$repo = (Get-Location).Path
$batch = Join-Path $repo ('.test-state/native-' + [guid]::NewGuid().ToString('N'))
$hub = Join-Path $batch 'hub'
$state = Join-Path $hub 'packs/balatro/core'
$pack = Join-Path $repo 'benchmarks/balatro'
$attempts = Join-Path (Split-Path $repo -Parent) ('attempts-' + [guid]::NewGuid().ToString('N'))
.venv-platform/Scripts/python.exe -I -B -m rhenium_balatro.maintenance prepare --pack $pack --state $state --controller-root C:/Touchstone/Balatro-PoC --reviewed-freeze-sha256 0a329c56fa5175a6afa56ca5177c8779cb71ecbffbf0e871943d697c8b763039
if ($LASTEXITCODE -ne 0) { throw 'Preparation failed; stop.' }
.venv-platform/Scripts/python.exe -I -B -m rhenium_balatro.maintenance smoke --pack $pack --state $state
if ($LASTEXITCODE -ne 0) { throw 'Smoke failed; preserve evidence and stop.' }
.venv-platform/Scripts/python.exe -B plugins/balatro/scripts/native_matrix_v1.py --repository $repo --state $hub --evidence (Join-Path $batch 'controls') --attempts $attempts --matrix controls
if ($LASTEXITCODE -ne 0) { throw 'Controls incomplete or mismatched; stop.' }
.venv-platform/Scripts/python.exe -B plugins/balatro/scripts/native_matrix_v1.py --repository $repo --state $hub --evidence (Join-Path $batch 'targeted') --attempts $attempts --matrix targeted
if ($LASTEXITCODE -ne 0) { throw 'Targeted matrix incomplete or mismatched; stop.' }
.venv-platform/Scripts/python.exe -I -B -m rhenium_balatro.maintenance audit --pack $pack --state $state
if ($LASTEXITCODE -ne 0) { throw 'Final runtime audit failed; stop.' }
.venv-platform/Scripts/python.exe -B plugins/balatro/scripts/preservation_audit_v1.py --repository $repo --controller C:/Touchstone/Balatro-PoC --original C:/Touchstone/SWE-Game --output (Join-Path $batch 'preservation.json')
if ($LASTEXITCODE -ne 0) { throw 'Preservation audit failed; stop.' }
.venv-platform/Scripts/python.exe -B plugins/balatro/scripts/summarize_native_v1.py --repository $repo --controls (Join-Path $batch 'controls') --targeted (Join-Path $batch 'targeted') --freeze (Join-Path $repo 'plugins/balatro/native-source-freeze-v1.json') --output (Join-Path $batch 'validation.json')
if ($LASTEXITCODE -ne 0) { throw 'Evidence verification failed; no acceptance.' }
```

Run commands sequentially and stop after any nonzero maintenance/matrix exit.
`pilot` selects one growth gold/base pair. The matrix itself accepts the expected
CLI exit 1 only for a complete semantic rejection matching that control's private
definition; arbitrary errors never pass. It creates fresh anonymous strict attempts,
copies only editable declared control files, and invokes the installed public CLI.
The participant-facing material and result contain no private assertions or gold.

The parent assigns the waiting sidecar to an owned Windows Job Object before
sending its one request. Normal engine shutdown uses original `poc.quit` and
Runtime.close. The outer 1800-second evaluation bound does not increase any RPC
timeout. A bound/log-size cancellation is observed between original calls, with
an 80-second cleanup grace. Forced closure or leftover descendants halts the
state; Ctrl-C/abnormal parent closure may force owned cleanup and cannot be called
a passing cancellation. No unrelated process is selected for termination.

The Job is a process-lifecycle mechanism, not a security sandbox. It follows the
[Windows Job Object API](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)
and uses KILL_ON_JOB_CLOSE without breakaway. Real native cleanup, protection and
fingerprint checks are required in addition to the harmless process unit test.

Raw responses, RPC logs, isolated save data and supervisor records are private
platform state. Publish only the sanitized reports. The conservative Hub doctor
does not launch a game or claim engine availability from a marker alone; use the
explicit preparation/audit/smoke workflow above. Reusing old smoke after adapter
changes is rejected. A halt marker is diagnostic evidence, never deleted to retry.
