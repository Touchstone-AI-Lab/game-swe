[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Rhenium
)

# Evaluate every pending submission of this kit once, plus one retry after an
# incomplete run. Results already present are never overwritten.
$ErrorActionPreference = "Stop"
$kit = $PSScriptRoot
$manifest = Get-Content -LiteralPath (Join-Path $kit "manifest.json") -Raw | ConvertFrom-Json
$executable = (Resolve-Path -LiteralPath $Rhenium).Path

foreach ($item in $manifest.attempts) {
    $attemptDir = Join-Path $kit ("attempts\" + $item.attemptId)
    $submission = Join-Path $kit $item.submission
    for ($index = 1; $index -le 2; $index++) {
        $output = Join-Path $attemptDir ("result-" + $index + ".json")
        if (-not (Test-Path -LiteralPath $output)) {
            Write-Host ("[" + $item.attemptId + "] run " + $index + ": " + $item.task)
            $printed = & $executable run $item.task $submission --profile $manifest.profile
            # Exit status 1 only means the submission did not pass; keep its output.
            [System.IO.File]::WriteAllText($output, ($printed -join "`n"), (New-Object System.Text.UTF8Encoding $false))
        }
        $complete = $false
        try {
            $value = Get-Content -LiteralPath $output -Raw | ConvertFrom-Json
            $complete = ($value.result.complete -eq $true)
        } catch {
            $complete = $false
        }
        if ($complete) { break }
    }
}
Write-Host "all attempts processed"
