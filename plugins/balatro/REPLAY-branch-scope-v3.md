# Branch v2 scoped maintenance replay

Use the unchanged installed 0.2.2 wheel and the preparation, source-review and
single-attempt commands in [REPLAY-branch-v2.md](REPLAY-branch-v2.md). The required
maintenance breadth is [scope v3](BRANCH-REGRESSION-SCOPE-v3.md), not the old
three-repetition/targeted plan. Each individual score still uses `full` with all
original cases. No model is called.

## Verify the delivered evidence without a game launch

From the staging checkout:

```powershell
$repo = (Get-Location).Path
$python = Join-Path $repo '.venv-platform/Scripts/python.exe'
$initial = Join-Path $repo '.test-state/brv2-final'
$batch = Join-Path $repo '.test-state/brv2-scope3'
$out = Join-Path $repo ('.test-state/recheck-scope-' + [guid]::NewGuid().ToString('N') + '.json')
& $python -B plugins/balatro/scripts/summarize_scope_v3.py --repository $repo --initial-batch $initial --batch $batch --freeze (Join-Path $repo 'plugins/balatro/branch-source-freeze-v4.json') --orchestration-freeze (Join-Path $repo 'plugins/balatro/branch-orchestration-freeze-v3.json') --output $out
if ($LASTEXITCODE -ne 0) { throw 'Evidence incomplete, changed or inconsistent; no acceptance.' }
```

This checks the real two-flow prefix of the superseded batch and the new eighteen
controls plus two review probes. The original 60-flow plan has no completion file.
Its intentional scope-stop marker remains in place. Never delete that marker or
modify the old plan to pretend it was a completed smaller matrix.

The final source freeze is v4. Its only delta from v2 isolates the native Windows
lock dependency in one mock-engine admission test; every assertion and the real
Windows lock/Job tests are preserved. The old test is archived and its hash bound
in v4. Product adapter, installed wheel, scenarios, grader and orchestration bytes
are unchanged, so the existing native results were reverified read-only into a
new `validation-v4.json`, without rerunning games or changing the old validation.
Final related tests: 192 passed. See [final report](BRANCH-READINESS-REPORT-v2.md)
and [checks](branch-checks-v4.json), including failed/unavailable repository gates.

## Execute the scoped suites afresh

Choose fresh state and attempt paths and prepare/smoke as in the operator guide.
Use a new state for every independent replay, never the stopped initial state.
Set `$repo`, `$python`, `$hub`, `$batch`, `$attempts`, and `$pwsh` as documented there.

```powershell
# Exactly two complete growth workflows through the real wrapper.
& $python -B plugins/balatro/scripts/native_matrix_v2.py --repository $repo --state $hub --evidence (Join-Path $batch 'growth-pair') --attempts $attempts --powershell $pwsh --matrix pilot
if ($LASTEXITCODE -ne 0) { throw 'Growth full pair incomplete or mismatched; stop.' }
# Eighteen complete workflows: the other nine gold/base pairs once each.
# Registers exact explicit reviews for durable-charge-v2 before scoring.
& $python -B plugins/balatro/scripts/native_scope_v3.py --repository $repo --state $hub --evidence (Join-Path $batch 'controls') --attempts $attempts --powershell $pwsh
if ($LASTEXITCODE -ne 0) { throw 'Remaining full pairs incomplete or mismatched; stop.' }
# Two new byte identities, explicitly reviewed and graded from real observations.
& $python -B plugins/balatro/scripts/reviewed_submission_probe_v2.py --repository $repo --state $hub --evidence (Join-Path $batch 'reviewed') --attempts $attempts --powershell $pwsh
if ($LASTEXITCODE -ne 0) { throw 'Review admission probe failed; stop.' }
& $python -I -B -m rhenium_balatro.maintenance audit --pack (Join-Path $repo 'benchmarks/balatro') --state (Join-Path $hub 'packs/balatro/core')
if ($LASTEXITCODE -ne 0) { throw 'Final integrity audit failed; stop.' }
```

These are 22 fresh workflows. Each driver validates expected behavior and complete
cases before writing its completion file. Preserve all three group plans,
records and hashes. The delivered-evidence verifier above deliberately accepts
only the recorded partial-prefix layout; it must not be pointed at a fresh
`growth-pair` completion or used to manufacture a matching historical layout.
Fresh replay has three complete groups rather than a superseded first group.

For ordinary authored submissions, use inspect-submission, explicit exact source
review and the printed anonymous score command once, rather than the operator
control drivers. Unknown code is never safe merely because a hash was recorded.

## Version and migration boundary

0.2.2 preserves the public catalog, anonymous submission and `full` scoring
contracts. The additive operator review/doctor interface uses private binding v2.
Bindings were already tied to exact adapter bytes and could not cross an adapter
revision; no in-place state migration or dependency repin is performed. Create a
fresh binding and matching smoke. Replaying native-v1 uses its preserved 0.2.1
wheel/source and v1 guide. This is not a change to core schemas or frozen task rules.
