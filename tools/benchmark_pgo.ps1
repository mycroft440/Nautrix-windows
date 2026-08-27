param(
    [Parameter(Mandatory=$true)][string]$BaselineBrowser,
    [Parameter(Mandatory=$true)][string]$PgoBrowser,
    [int]$Runs = 5,
    [int]$ProfileSeconds = 30,
    [string]$OutputDir = "$env:LOCALAPPDATA\Nautrix\pgo-comparison"
)

$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$bench = Join-Path $PSScriptRoot 'benchmark_navigation.ps1'
$profiler = Join-Path $PSScriptRoot 'profile_browser.ps1'
$gate = Join-Path $PSScriptRoot 'performance_gate.ps1'

$baselineCsv = Join-Path $OutputDir 'baseline.csv'
$pgoCsv = Join-Path $OutputDir 'pgo.csv'
$baselineProfile = Join-Path $OutputDir 'baseline-processes.csv'
$pgoProfile = Join-Path $OutputDir 'pgo-processes.csv'

& $bench -Browser $BaselineBrowser -Runs $Runs -Output $baselineCsv
& $bench -Browser $PgoBrowser -Runs $Runs -Output $pgoCsv
& $profiler -Browser $BaselineBrowser -Seconds $ProfileSeconds -Output $baselineProfile
& $profiler -Browser $PgoBrowser -Seconds $ProfileSeconds -Output $pgoProfile

$baselineSummary = Join-Path $OutputDir 'baseline-summary.csv'
$pgoSummary = Join-Path $OutputDir 'pgo-summary.csv'
& $gate `
    -BaselineSummary $baselineSummary `
    -CandidateSummary $pgoSummary `
    -BaselineProfile $baselineProfile `
    -CandidateProfile $pgoProfile `
    -RequireImprovement `
    -Output (Join-Path $OutputDir 'pgo-performance-gate.json')

Write-Host "[Nautrix] Baseline/PGO results and approval gate: $OutputDir"
