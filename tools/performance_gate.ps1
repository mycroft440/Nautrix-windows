[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$BaselineSummary,
    [Parameter(Mandatory=$true)][string]$CandidateSummary,
    [string]$BaselineProfile,
    [string]$CandidateProfile,
    [double]$MaxTailRegressionPct = 5.0,
    [double]$MaxMemoryRegressionPct = 5.0,
    [double]$MaxCpuRegressionPct = 5.0,
    [switch]$RequireImprovement,
    [string]$Output
)

$ErrorActionPreference = 'Stop'
foreach ($path in @($BaselineSummary, $CandidateSummary)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing benchmark summary: $path" }
}
if (($BaselineProfile -and -not $CandidateProfile) -or ($CandidateProfile -and -not $BaselineProfile)) {
    throw 'BaselineProfile and CandidateProfile must be supplied together.'
}

function Get-PctChange([double]$Baseline, [double]$Candidate) {
    if ($Baseline -eq 0) {
        if ($Candidate -eq 0) { return 0.0 }
        return [double]::PositiveInfinity
    }
    return (($Candidate - $Baseline) / $Baseline) * 100.0
}

function Get-ProfileStats([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Missing process profile: $Path" }
    $rows = @(Import-Csv -LiteralPath $Path)
    if ($rows.Count -eq 0) { throw "Empty process profile: $Path" }

    $peakWorking = 0.0
    $peakPrivate = 0.0
    foreach ($group in ($rows | Group-Object timestamp)) {
        $working = [double](($group.Group | Measure-Object -Property working_set_mb -Sum).Sum)
        $private = [double](($group.Group | Measure-Object -Property private_mb -Sum).Sum)
        if ($working -gt $peakWorking) { $peakWorking = $working }
        if ($private -gt $peakPrivate) { $peakPrivate = $private }
    }

    $cpu = 0.0
    foreach ($pidGroup in ($rows | Group-Object pid)) {
        [double[]]$samples = @($pidGroup.Group | ForEach-Object { [double]$_.cpu_seconds })
        if ($samples.Count -gt 0) {
            $cpu += (($samples | Measure-Object -Maximum).Maximum - ($samples | Measure-Object -Minimum).Minimum)
        }
    }

    [pscustomobject]@{
        peak_working_set_mb = [math]::Round($peakWorking, 3)
        peak_private_mb = [math]::Round($peakPrivate, 3)
        cpu_seconds_delta = [math]::Round($cpu, 3)
    }
}

$baseline = @(Import-Csv -LiteralPath $BaselineSummary)
$candidate = @(Import-Csv -LiteralPath $CandidateSummary)
if ($baseline.Count -eq 0 -or $candidate.Count -eq 0) { throw 'Benchmark summary cannot be empty.' }

$candidateByUrl = @{}
foreach ($row in $candidate) { $candidateByUrl[[string]$row.url] = $row }
$violations = [System.Collections.Generic.List[string]]::new()
$improvements = [System.Collections.Generic.List[string]]::new()
$comparisons = [System.Collections.Generic.List[object]]::new()

foreach ($base in $baseline) {
    $url = [string]$base.url
    if (-not $candidateByUrl.ContainsKey($url)) {
        $violations.Add("candidate missing URL: $url")
        continue
    }
    $cand = $candidateByUrl[$url]
    if ([int]$base.failures -ne 0 -or [int]$cand.failures -ne 0) {
        $violations.Add("navigation failures present for $url (baseline=$($base.failures), candidate=$($cand.failures))")
    }

    $p95Change = Get-PctChange ([double]$base.p95_ms) ([double]$cand.p95_ms)
    $p99Change = Get-PctChange ([double]$base.p99_ms) ([double]$cand.p99_ms)
    if ($p95Change -gt $MaxTailRegressionPct) { $violations.Add("p95 regression $([math]::Round($p95Change,2))% for $url") }
    if ($p99Change -gt $MaxTailRegressionPct) { $violations.Add("p99 regression $([math]::Round($p99Change,2))% for $url") }
    if ($p95Change -lt -1.0) { $improvements.Add("p95 improved for $url") }
    if ($p99Change -lt -1.0) { $improvements.Add("p99 improved for $url") }

    $comparisons.Add([pscustomobject]@{
        url = $url
        baseline_p95_ms = [double]$base.p95_ms
        candidate_p95_ms = [double]$cand.p95_ms
        p95_change_pct = [math]::Round($p95Change, 3)
        baseline_p99_ms = [double]$base.p99_ms
        candidate_p99_ms = [double]$cand.p99_ms
        p99_change_pct = [math]::Round($p99Change, 3)
    })
}

$profileComparison = $null
if ($BaselineProfile -and $CandidateProfile) {
    $baseProfile = Get-ProfileStats $BaselineProfile
    $candProfile = Get-ProfileStats $CandidateProfile
    $workingChange = Get-PctChange $baseProfile.peak_working_set_mb $candProfile.peak_working_set_mb
    $privateChange = Get-PctChange $baseProfile.peak_private_mb $candProfile.peak_private_mb
    $cpuChange = Get-PctChange $baseProfile.cpu_seconds_delta $candProfile.cpu_seconds_delta

    if ($workingChange -gt $MaxMemoryRegressionPct) { $violations.Add("working-set regression $([math]::Round($workingChange,2))%") }
    if ($privateChange -gt $MaxMemoryRegressionPct) { $violations.Add("private-memory regression $([math]::Round($privateChange,2))%") }
    if ($cpuChange -gt $MaxCpuRegressionPct) { $violations.Add("CPU regression $([math]::Round($cpuChange,2))%") }
    if ($workingChange -lt -1.0) { $improvements.Add('peak working set improved') }
    if ($privateChange -lt -1.0) { $improvements.Add('peak private memory improved') }
    if ($cpuChange -lt -1.0) { $improvements.Add('CPU seconds improved') }

    $profileComparison = [pscustomobject]@{
        baseline = $baseProfile
        candidate = $candProfile
        working_set_change_pct = [math]::Round($workingChange, 3)
        private_memory_change_pct = [math]::Round($privateChange, 3)
        cpu_change_pct = [math]::Round($cpuChange, 3)
    }
}

if ($RequireImprovement -and $improvements.Count -eq 0) {
    $violations.Add('candidate has no measured improvement above the 1% noise floor')
}

$result = [ordered]@{
    passed = ($violations.Count -eq 0)
    max_tail_regression_pct = $MaxTailRegressionPct
    max_memory_regression_pct = $MaxMemoryRegressionPct
    max_cpu_regression_pct = $MaxCpuRegressionPct
    require_improvement = [bool]$RequireImprovement
    improvements = @($improvements)
    violations = @($violations)
    navigation = @($comparisons)
    resources = $profileComparison
}
if (-not $Output) {
    $Output = Join-Path (Split-Path -Parent $CandidateSummary) 'performance-gate.json'
}
$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Output -Encoding utf8

if ($violations.Count -gt 0) {
    foreach ($violation in $violations) { [Console]::Error.WriteLine("[Nautrix gate] $violation") }
    throw "Nautrix performance gate failed. Report: $Output"
}
Write-Host "[Nautrix] Performance gate passed: $Output"
