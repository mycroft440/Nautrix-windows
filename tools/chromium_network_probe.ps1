param(
    [Parameter(Mandatory=$true)][string]$Browser,
    [string[]]$Urls = @('https://www.mexc.com','https://api.mexc.com'),
    [string]$OutputDir = "$env:LOCALAPPDATA\Nautrix\network-probes"
)

$ErrorActionPreference = 'Stop'
if (!(Test-Path $Browser)) { throw "Browser not found: $Browser" }
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$analyzer = Join-Path $PSScriptRoot 'analyze_netlog.py'
$rows = @()

foreach ($url in $Urls) {
    $safe = ($url -replace '^https?://','' -replace '[^A-Za-z0-9.-]','_')
    $profile = Join-Path $env:TEMP "nautrix-netprobe-$PID-$([guid]::NewGuid().ToString('N'))"
    $netlog = Join-Path $OutputDir "$safe-netlog.json"
    $summary = Join-Path $OutputDir "$safe-summary.csv"
    try {
        $sw = [Diagnostics.Stopwatch]::StartNew()
        $p = Start-Process -FilePath $Browser -ArgumentList @(
            '--headless=new',
            "--user-data-dir=$profile",
            "--log-net-log=$netlog",
            '--net-log-capture-mode=Default',
            '--dump-dom',
            $url
        ) -NoNewWindow -PassThru -Wait
        $sw.Stop()
        if ($p.ExitCode -ne 0) {
            throw "Chromium network probe failed for $url with exit code $($p.ExitCode)."
        }
        if (-not (Test-Path -LiteralPath $netlog -PathType Leaf) -or
            (Get-Item -LiteralPath $netlog).Length -eq 0) {
            throw "Chromium network probe did not produce a NetLog for $url."
        }
        python $analyzer $netlog --output $summary
        if ($LASTEXITCODE -ne 0) { throw "NetLog analysis failed for $url" }
        if (-not (Test-Path -LiteralPath $summary -PathType Leaf)) {
            throw "NetLog analysis did not produce a summary for $url."
        }
        $rows += [pscustomobject]@{
            url = $url
            total_elapsed_ms = [math]::Round($sw.Elapsed.TotalMilliseconds,3)
            exit_code = $p.ExitCode
            netlog = $netlog
            summary = $summary
        }
    } finally {
        Remove-Item -Recurse -Force $profile -ErrorAction SilentlyContinue
    }
}
$rows | Export-Csv -NoTypeInformation -Encoding utf8 (Join-Path $OutputDir 'navigation.csv')
if (@($rows | Where-Object exit_code -ne 0).Count -ne 0) {
    throw 'One or more Chromium network probes failed.'
}
Write-Host "[Nautrix] Chromium network probes: $OutputDir"
