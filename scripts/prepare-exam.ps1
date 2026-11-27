[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$TaskKey,
    [Parameter(Mandatory = $true, Position = 1)]
    [string]$AttemptDirectory,
    [Parameter(Position = 2)]
    [ValidateSet("strict", "practice")]
    [string]$Mode = "strict"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$parent = Split-Path -Parent $AttemptDirectory
if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
    throw "attempt parent directory does not exist: $parent"
}
$attempt = [System.IO.Path]::GetFullPath($AttemptDirectory)
$rootPrefix = $root.TrimEnd("\") + "\"
if ($attempt -eq $root -or $attempt.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "attempt must be outside the benchmark repository"
}
if (Test-Path -LiteralPath $attempt) {
    $item = Get-Item -LiteralPath $attempt -Force
    if (-not $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw "attempt path must be a real directory"
    }
    if (Get-ChildItem -LiteralPath $attempt -Force | Select-Object -First 1) {
        throw "attempt directory is not empty: $attempt"
    }
} else {
    New-Item -ItemType Directory -Path $attempt | Out-Null
}

$state = if ($env:RHENIUM_STATE_DIR) { $env:RHENIUM_STATE_DIR } else { Join-Path $root ".rhenium\hub" }
$env:RHENIUM_ROOT = $root
$env:RHENIUM_BENCHMARK_PATH = if ($env:RHENIUM_BENCHMARK_PATH) { $env:RHENIUM_BENCHMARK_PATH } else { Join-Path $root "benchmarks" }
$env:RHENIUM_STATE_DIR = $state
$env:RHENIUM_CACHE_DIR = if ($env:RHENIUM_CACHE_DIR) { $env:RHENIUM_CACHE_DIR } else { Join-Path $state "cache" }
$env:RHENIUM_DATABASE_URL = if ($env:RHENIUM_DATABASE_URL) { $env:RHENIUM_DATABASE_URL } else { "sqlite:///$state/state.sqlite" }

$rhenium = Get-Command rhenium -CommandType Application -ErrorAction Stop | Select-Object -First 1
$scorer = Join-Path $PSScriptRoot "score-exam.ps1"
& $rhenium.Source prepare-attempt $TaskKey $attempt --mode $Mode --score-command $scorer | Out-Null
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
Write-Output "Prepared anonymous $Mode attempt at $attempt"
Write-Output "Start the coding agent in that directory with the contents of PROMPT.md."
