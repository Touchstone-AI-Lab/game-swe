# Balatro operator workflow

Use the [current support matrix](../../docs/games/balatro-branch-v2.md) for capability
claims. Plugin 0.2.2 implements local `honest` preparation, sealed submission and
real scoring on the approved, separately prepared, fixed Windows desktop host.
It does not acquire or install the game, bootstrap another host, or isolate hostile
code. Core/plugin Python is 3.12; the reviewed external controller remains 3.13.12.

These command interfaces are checked against source, `--help`, unit contracts and
the prior real wrapper records. The present documentation/CI maintenance does not
run `prepare`, `smoke`, review authorization or scoring, and does not start games.
Variable placeholders below require operator-supplied reviewed values; they are
not a new-host recipe or a claim that arbitrary paths were validated.

## Discovery and read-only readiness

With the plugin and contract-compatible core installed, from the repository root:

```powershell
$repo = (Get-Location).Path
$python = Join-Path $repo '.venv-platform/Scripts/python.exe'
& $python -I -B -m rhenium.cli games
& $python -I -B -m rhenium.cli packs --game balatro
& $python -I -B -m rhenium.cli tasks --game balatro --pack core
```

These commands read benchmark inputs; the Hub can initialize its state/database
outside the pack. They do not prove engine readiness. Discovery should show
`balatro`, `balatro/core` and ten unique task keys.

For an **existing** operator state, the plugin doctor is read-only and does not
launch a game or repair anything:

```powershell
$pack = Join-Path $repo 'benchmarks/balatro'
$state = '<existing reviewed pack state directory outside the pack>'
& $python -I -B -m rhenium_balatro.maintenance doctor --pack $pack --state $state
```

Doctor returns 0 only for matching verified readiness. Code 2 is unavailable or
action-required. Missing/stale bindings, drift, unmatched smoke, unsupported OS
or a halt marker are not success. Keep halt/protection markers for investigation.

## Explicit binding and matching smoke

Only the approved fixed host can use this route. A fresh private state must be
outside the read-only pack. The operator supplies the already reviewed controller
root and source-freeze digest; inspection or a digest alone is not source review.

```powershell
$batch = Join-Path $repo ('.test-state/balatro-' + [guid]::NewGuid().ToString('N'))
$hub = Join-Path $batch 'hub'
$state = Join-Path $hub 'packs/balatro/core'
$controllerRoot = '<already prepared and approved fixed controller root>'
$reviewedFreeze = '<exact SHA-256 of its reviewed source freeze>'
& $python -I -B -m rhenium_balatro.maintenance prepare --pack $pack --state $state --controller-root $controllerRoot --reviewed-freeze-sha256 $reviewedFreeze
if ($LASTEXITCODE -ne 0) { throw 'Binding failed; stop and preserve evidence.' }
# This explicit operation starts a real, visible game; it is not a CI check.
& $python -I -B -m rhenium_balatro.maintenance smoke --pack $pack --state $state
if ($LASTEXITCODE -ne 0) { throw 'Smoke incomplete; stop and investigate.' }
& $python -I -B -m rhenium_balatro.maintenance doctor --pack $pack --state $state
if ($LASTEXITCODE -ne 0) { throw 'Runtime not ready.' }
```

A historical smoke file with different fingerprints does not qualify. Preparation
does not download, upgrade or repin inputs; bindings are not silently overwritten
or migrated. Matching readiness does not waive the repeated byte/protection checks
at execution. Serial visible runs use gamespeed=1, FAST=0 and HEADLESS=0.

## Anonymous attempt, actual source review and one score

The trusted operator configures the existing core state, then prepares a new
attempt at a fresh location outside the private repository:

```powershell
$env:RHENIUM_ROOT = $repo
$env:RHENIUM_STATE_DIR = $hub
$env:RHENIUM_CACHE_DIR = Join-Path $batch 'cache'
$env:RHENIUM_DATABASE_URL = 'sqlite:///' + (Join-Path $hub 'state.sqlite')
$env:RHENIUM_BENCHMARK_PATH = $pack
$env:PATH = (Split-Path $python -Parent) + [IO.Path]::PathSeparator + $env:PATH
$attempt = '<fresh anonymous attempt directory outside the private repository>'
$task = 'growth-v2'
& $python -I -B -m rhenium.cli prepare-attempt ('balatro/core/' + $task) $attempt --score-command (Join-Path $repo 'scripts/score-exam.ps1') --mode strict
if ($LASTEXITCODE -ne 0) { throw 'Attempt preparation failed.' }
```

After implementation, review every submitted executable source file. Inspect the
exact submitted bytes and record the same seal only after that review:

```powershell
& $python -I -B -m rhenium_balatro.maintenance inspect-submission --pack $pack --state $state --task $task --submission $attempt
if ($LASTEXITCODE -ne 0) { throw 'Submission inspection failed.' }
$reviewedHash = '<submissionSha256 for the source actually reviewed>'
& $python -I -B -m rhenium_balatro.maintenance review-submission --pack $pack --state $state --task $task --submission $attempt --reviewed-submission-sha256 $reviewedHash --source-reviewed
if ($LASTEXITCODE -ne 0) { throw 'Exact-byte review not accepted.' }
```

Inspection checks allowed/immutable files and computes fingerprints; it does not
review behavior or authorize code. Execute the **exact anonymous wrapper command
printed in the attempt's PROMPT.md once** after review. Do not replace it with a
private evaluator command. A changed task, source, adapter, assets or environment
invalidates authorization. The operator's Hub variables are not the game's
environment; the runner still constructs its validated minimal environment.

Code 0 means a complete pass. A nonzero scorer exit alone is insufficient to
classify a result: check `complete`, `category` and `reason`. A fully observed
business mismatch is a complete behavior rejection; missing cases, timeout,
protocol/environment/cleanup failures remain incomplete. Unreviewed source is
incomplete with `submission_review_required` and does not launch. Preserve the
private operation evidence, investigate, and do not retry an unconfirmed action
or rescore the same strict attempt. No arbitrary downloaded mod is authorized by
these examples. `untrusted` requires a separate host provider and has no local fallback.

## Recovery and evidence boundaries

Save restoration requires a fresh process, complete seeded initialization, then
one load with a complete response; blank MENU direct load remains unsupported.
Headphones disconnected is the operator's agreed recovery condition, not a proven
permanent fix or continuous device monitoring. Never change audio/system settings
or delete protection/halt markers to obtain a pass.

Use the [versioned report](BRANCH-READINESS-REPORT-v2.md),
[sanitized validation](validation-branch-v2.json), and
[historical scoped replay](REPLAY-branch-scope-v3.md) for the 22/58/948 batch.
Replay scripts require the original private evidence/approved runtime; they are
not CI commands. Raw logs, saves, local paths, binding files and temporary wheels
stay in operator state and are not distributed. The old guides remain byte-exact
records; their fixed machine paths describe that historical host only.
