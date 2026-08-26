param(
    [Parameter(Mandatory=$true)][string]$BaselineBrowser,
    [Parameter(Mandatory=$true)][string]$PgoBrowser,
    [int]$Runs = 3,
    [string]$OutputDir = "$env:LOCALAPPDATA\Nautrix\pgo-comparison"
)

$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$bench = Join-Path $PSScriptRoot 'benchmark_navigation.ps1'
& $bench -Browser $BaselineBrowser -Runs $Runs -Output (Join-Path $OutputDir 'baseline.csv')
& $bench -Browser $PgoBrowser -Runs $Runs -Output (Join-Path $OutputDir 'pgo.csv')
Write-Host "[Nautrix] Baseline/PGO results: $OutputDir"
