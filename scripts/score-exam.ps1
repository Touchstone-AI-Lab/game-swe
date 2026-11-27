[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$SubmissionDirectory,
    [string]$Profile,
    [ValidateSet("honest", "untrusted")]
    [string]$SecurityMode,
    [string]$HostProvider,
    [string]$HostImage
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$submission = (Resolve-Path -LiteralPath $SubmissionDirectory).Path
$rootPrefix = $root.TrimEnd("\") + "\"
$submissionPrefix = $submission.TrimEnd("\") + "\"
if ($submission -eq $root -or $submission.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "submission must be outside the benchmark repository"
}
if ($root.StartsWith($submissionPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "submission must not contain the benchmark repository"
}

$state = if ($env:RHENIUM_STATE_DIR) { $env:RHENIUM_STATE_DIR } else { Join-Path $root ".rhenium\hub" }
$env:RHENIUM_ROOT = $root
$env:RHENIUM_BENCHMARK_PATH = if ($env:RHENIUM_BENCHMARK_PATH) { $env:RHENIUM_BENCHMARK_PATH } else { Join-Path $root "benchmarks" }
$env:RHENIUM_STATE_DIR = $state
$env:RHENIUM_CACHE_DIR = if ($env:RHENIUM_CACHE_DIR) { $env:RHENIUM_CACHE_DIR } else { Join-Path $state "cache" }
$env:RHENIUM_DATABASE_URL = if ($env:RHENIUM_DATABASE_URL) { $env:RHENIUM_DATABASE_URL } else { "sqlite:///$state/state.sqlite" }

$arguments = @("run-attempt", $submission)
if ($Profile) {
    $arguments += @("--profile", $Profile)
}
$selectedSecurityMode = if ($SecurityMode) {
    $SecurityMode
} elseif ($env:RHENIUM_EVALUATION_SECURITY_MODE) {
    $env:RHENIUM_EVALUATION_SECURITY_MODE
} else {
    "honest"
}
$selectedHostProvider = if ($HostProvider) { $HostProvider } else { $env:RHENIUM_EVALUATION_HOST_PROVIDER }
$selectedHostImage = if ($HostImage) { $HostImage } else { $env:RHENIUM_EVALUATION_HOST_IMAGE }
if ($selectedSecurityMode -notin @("honest", "untrusted")) {
    throw "security mode must be honest or untrusted"
}
if ($selectedSecurityMode -eq "untrusted") {
    if (-not $selectedHostProvider) { throw "untrusted mode requires -HostProvider" }
    if (-not $selectedHostImage) { throw "untrusted mode requires -HostImage" }
} elseif ($selectedHostProvider -or $selectedHostImage) {
    throw "host options require -SecurityMode untrusted"
}
if ($selectedSecurityMode -eq "untrusted") {
    $arguments += @(
        "--security-mode", "untrusted",
        "--host-provider", $selectedHostProvider,
        "--host-image", $selectedHostImage
    )
}
$rhenium = Get-Command rhenium -CommandType Application -ErrorAction Stop | Select-Object -First 1
& $rhenium.Source @arguments
exit $LASTEXITCODE
