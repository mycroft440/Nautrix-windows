param(
    [Parameter(Mandatory=$true)][string]$Browser,
    [string[]]$Urls = @(
        'https://example.com',
        'https://www.google.com',
        'https://www.mexc.com',
        'https://www.binance.com',
        'https://www.bybit.com',
        'https://www.okx.com',
        'https://www.tradingview.com'
    ),
    [int]$Runs = 10,
    [string]$Output = "$env:LOCALAPPDATA\Nautrix\navigation-benchmark.csv"
)

$ErrorActionPreference = 'Stop'
if (!(Test-Path $Browser)) { throw "Browser not found: $Browser" }
if ($Runs -lt 1) { throw 'Runs must be >= 1' }
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Output) | Out-Null

function Get-Percentile([double[]]$Values, [double]$Percentile) {
    if (!$Values -or $Values.Count -eq 0) { return [double]::NaN }
    $sorted = @($Values | Sort-Object)
    $index = [math]::Ceiling($Percentile * $sorted.Count) - 1
    $index = [math]::Max(0, [math]::Min($index, $sorted.Count - 1))
    return [double]$sorted[$index]
}

$records = [System.Collections.Generic.List[object]]::new()
for ($r = 1; $r -le $Runs; $r++) {
    foreach ($url in $Urls) {
        $profile = Join-Path $env:TEMP "nautrix-bench-$PID-$r-$([guid]::NewGuid().ToString('N'))"
        try {
            $sw = [Diagnostics.Stopwatch]::StartNew()
            $p = Start-Process -FilePath $Browser -ArgumentList @(
                '--headless=new',
                '--disable-gpu',
                "--user-data-dir=$profile",
                '--dump-dom',
                $url
            ) -NoNewWindow -PassThru -Wait
            $sw.Stop()
            $records.Add([pscustomobject]@{
                run = $r
                url = $url
                elapsed_ms = [math]::Round($sw.Elapsed.TotalMilliseconds, 3)
                exit_code = $p.ExitCode
            })
        } finally {
            Remove-Item -Recurse -Force $profile -ErrorAction SilentlyContinue
        }
    }
}

$records | Export-Csv -LiteralPath $Output -NoTypeInformation -Encoding utf8
$summaryPath = [IO.Path]::Combine(
    [IO.Path]::GetDirectoryName($Output),
    ([IO.Path]::GetFileNameWithoutExtension($Output) + '-summary.csv')
)

$summary = foreach ($group in ($records | Group-Object url)) {
    $ok = @($group.Group | Where-Object exit_code -eq 0)
    $values = [double[]]@($ok | ForEach-Object elapsed_ms)
    [pscustomobject]@{
        url = $group.Name
        samples = $group.Count
        success_samples = $ok.Count
        failures = $group.Count - $ok.Count
        min_ms = if ($values.Count) { [math]::Round(($values | Measure-Object -Minimum).Minimum, 3) } else { [double]::NaN }
        mean_ms = if ($values.Count) { [math]::Round(($values | Measure-Object -Average).Average, 3) } else { [double]::NaN }
        p50_ms = [math]::Round((Get-Percentile $values 0.50), 3)
        p95_ms = [math]::Round((Get-Percentile $values 0.95), 3)
        p99_ms = [math]::Round((Get-Percentile $values 0.99), 3)
        max_ms = if ($values.Count) { [math]::Round(($values | Measure-Object -Maximum).Maximum, 3) } else { [double]::NaN }
    }
}
$summary | Export-Csv -LiteralPath $summaryPath -NoTypeInformation -Encoding utf8

Write-Host "[Nautrix] Navigation samples: $Output"
Write-Host "[Nautrix] Navigation p50/p95/p99 summary: $summaryPath"
