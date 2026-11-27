# Balatro plugin 0.2.2 operator guide

Current maintenance acceptance uses the user-approved
[scope amendment v3](BRANCH-REGRESSION-SCOPE-v3.md): ten gold/base pairs once,
plus two reviewed new byte identities. The broad matrix commands below preserve
the original v2 plan for reference; they are not a requirement to repeat 76
flows for this maintenance change. Current evidence verification and scoped
replay commands are in [REPLAY-branch-scope-v3.md](REPLAY-branch-scope-v3.md).

This is trusted local `honest` development on the already prepared controlled
Windows host. No command acquires a game, installs system tools, changes fixed
dependencies or starts a model. Keep the existing licensed runtime and Python
3.13 controller unchanged; install this plugin only in the separate core-compatible
Python 3.12 environment. The plugin wheel contains Python adapter code only.

The current source-review and runtime binding format is v2. A v1 binding is not
silently migrated: use fresh state and a new matching smoke. Old native-v1 source
and evidence are preserved; replay v1 with its archived source/wheel and its
original guide, not with the v2 adapter.

## Prepare and inspect runtime

From the staging checkout with the reviewed 0.2.2 wheel already installed:

```powershell
$repo = (Get-Location).Path
$python = Join-Path $repo '.venv-platform/Scripts/python.exe'
$pack = Join-Path $repo 'benchmarks/balatro'
$batch = Join-Path $repo ('.test-state/branch-v2-' + [guid]::NewGuid().ToString('N'))
$hub = Join-Path $batch 'hub'
$state = Join-Path $hub 'packs/balatro/core'
$attempts = Join-Path (Split-Path $repo -Parent) ('attempts-' + [guid]::NewGuid().ToString('N'))
$pwsh = (Get-Command pwsh -CommandType Application).Source
& $python -I -B -m rhenium_balatro.maintenance prepare --pack $pack --state $state --controller-root C:/Touchstone/Balatro-PoC --reviewed-freeze-sha256 0a329c56fa5175a6afa56ca5177c8779cb71ecbffbf0e871943d697c8b763039
if ($LASTEXITCODE -ne 0) { throw 'Preparation failed; stop.' }
& $python -I -B -m rhenium_balatro.maintenance smoke --pack $pack --state $state
if ($LASTEXITCODE -ne 0) { throw 'Smoke incomplete; preserve evidence and stop.' }
& $python -I -B -m rhenium_balatro.maintenance doctor --pack $pack --state $state
if ($LASTEXITCODE -ne 0) { throw 'Runtime is not ready; stop.' }
```

Doctor hashes the fixed external inputs and matching smoke and checks the protected
baseline without launching the game or writing state/cache. A present stale marker
is insufficient. It returns code 0 only for verified readiness; code 2 is an
action-required/unavailable result, not a passing smoke. Runtime execution repeats
the byte and protection checks; readiness is not a waiver for subsequent drift.

## Review and score a new authored submission

Use a new anonymous attempt outside the private repository. The operator sets the
existing core state/cache/database/pack variables in the trusted scorer environment,
and puts the installed platform `rhenium` executable on that environment's PATH.
Do not forward these variables or arbitrary host variables to game processes.

```powershell
$env:RHENIUM_ROOT = $repo
$env:RHENIUM_STATE_DIR = $hub
$env:RHENIUM_CACHE_DIR = Join-Path $batch 'cache'
$env:RHENIUM_DATABASE_URL = 'sqlite:///' + (Join-Path $hub 'state.sqlite')
$env:RHENIUM_BENCHMARK_PATH = $pack
$env:PATH = (Split-Path $python -Parent) + [IO.Path]::PathSeparator + $env:PATH
New-Item -ItemType Directory -Path $attempts -Force | Out-Null
$attempt = Join-Path $attempts ([guid]::NewGuid().ToString('N'))
# The operator chooses a catalog task. Canonical identity stays outside the attempt.
$task = 'growth-v2'
& $python -I -B -m rhenium.cli prepare-attempt ('balatro/core/' + $task) $attempt --score-command (Join-Path $repo 'scripts/score-exam.ps1') --mode strict
if ($LASTEXITCODE -ne 0) { throw 'Attempt preparation failed.' }
# Author repairs under $attempt/starter. The operator then reviews those exact source bytes.
& $python -I -B -m rhenium_balatro.maintenance inspect-submission --pack $pack --state $state --task $task --submission $attempt
```

Inspection only validates the public file allowlist/immutable files and prints
the current seal. It does not inspect source behavior, declare safety or grant
permission. After actually reviewing the source, supply its exact printed
`submissionSha256` to this explicit operator action:

```powershell
$reviewedHash = '<exact SHA-256 of the source the operator reviewed>'
& $python -I -B -m rhenium_balatro.maintenance review-submission --pack $pack --state $state --task $task --submission $attempt --reviewed-submission-sha256 $reviewedHash --source-reviewed
if ($LASTEXITCODE -ne 0) { throw 'Source review record not accepted.' }
& $pwsh -NoProfile -NonInteractive -File (Join-Path $repo 'scripts/score-exam.ps1') $attempt -Profile full -SecurityMode honest
```

Score the strict attempt once. Code 0 means a complete pass; code 1 can mean a
complete behavior rejection or an incomplete result: inspect `complete`, `category`
and `reason`. Valid but unreviewed code returns `submission_review_required` and
does not launch. A content/task/runtime/adapter change invalidates review. Review
records live under private state and contain identities, not expected answers.
The grader independently derives candidate fingerprints and reads actual engine
results; it does not recognize a gold/base role to decide the score.

The existing original control allowlist remains authorized for maintenance.
No arbitrary downloaded mod or hostile submission is made safe by a review file.
Explicit `untrusted` requests remain routed by core; unavailable host providers
never fall back to this local evaluator.

## Reproduce the branch control matrices

These operator-only commands use authored controls, never a model. Each creates
new anonymous attempts and invokes the actual `score-exam.ps1` once per attempt.
They reuse the frozen scenarios and original record checker; every targeted role
also receives an explicit review record.

```powershell
& $python -B plugins/balatro/scripts/native_matrix_v2.py --repository $repo --state $hub --evidence (Join-Path $batch 'controls') --attempts $attempts --powershell $pwsh --matrix controls
if ($LASTEXITCODE -ne 0) { throw 'Controls incomplete or unexpected; stop.' }
& $python -B plugins/balatro/scripts/native_matrix_v2.py --repository $repo --state $hub --evidence (Join-Path $batch 'targeted') --attempts $attempts --powershell $pwsh --matrix targeted
if ($LASTEXITCODE -ne 0) { throw 'Targeted regression incomplete or unexpected; stop.' }
& $python -B plugins/balatro/scripts/reviewed_submission_probe_v2.py --repository $repo --state $hub --evidence (Join-Path $batch 'reviewed') --attempts $attempts --powershell $pwsh
if ($LASTEXITCODE -ne 0) { throw 'New submission review path failed; stop.' }
& $python -I -B -m rhenium_balatro.maintenance audit --pack $pack --state $state
if ($LASTEXITCODE -ne 0) { throw 'Final runtime audit failed; stop.' }
& $python -B plugins/balatro/scripts/preservation_audit_v1.py --repository $repo --controller C:/Touchstone/Balatro-PoC --original C:/Touchstone/SWE-Game --output (Join-Path $batch 'preservation.json')
if ($LASTEXITCODE -ne 0) { throw 'Preservation audit failed; stop.' }
& $python -B plugins/balatro/scripts/summarize_branch_v2.py --repository $repo --batch $batch --freeze (Join-Path $repo 'plugins/balatro/branch-source-freeze-v2.json') --output (Join-Path $batch 'validation.json')
if ($LASTEXITCODE -ne 0) { throw 'Evidence verification failed; no acceptance.' }
```

The last probe appends only a Lua comment to a gold/base copy to obtain previously
unlisted byte identities. It verifies review/admission and semantic scoring, not
additional task coverage or a new correct implementation. Original candidates
and frozen task inputs stay untouched. Never retry a failed/unconfirmed action,
delete halt/protection markers, increase timeouts or repin components to proceed.

Raw RPC results, isolated saves and logs stay private under the selected state.
Publish only sanitized reports, source/artifact manifests and derived counts.
