param(
    [Parameter(Mandatory=$true)][string]$Browser,
    [Parameter(Mandatory=$true)][string]$Launcher,
    [string]$ConfigDir = (Join-Path (Split-Path -Parent $PSScriptRoot) 'config'),
    [string]$OutputDir = "$env:LOCALAPPDATA\Nautrix\smoke"
)

$ErrorActionPreference = 'Stop'
if (!(Test-Path $Browser)) { throw "Browser not found: $Browser" }
if (!(Test-Path $Launcher)) { throw "Launcher not found: $Launcher" }
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$version = @(& $Browser --version 2>&1)
if ($LASTEXITCODE -ne 0 -or -not ($version -join '').Trim()) {
    throw "Browser --version failed with exit code $LASTEXITCODE."
}
$version | Set-Content -Encoding utf8 (Join-Path $OutputDir 'version.txt')

$checks = @(
    [pscustomobject]@{ url = 'data:text/html,<title>Nautrix Smoke</title><h1 id="marker">nautrix-smoke-ok</h1>'; expected = 'nautrix-smoke-ok'; name = 'local' },
    [pscustomobject]@{ url = 'https://example.com'; expected = 'Example Domain'; name = 'example-com' },
    [pscustomobject]@{ url = 'https://www.google.com'; expected = '<html'; name = 'google-com' }
)
$rows = @()
foreach ($check in $checks) {
    $profile = Join-Path $env:TEMP "nautrix-smoke-$PID-$([guid]::NewGuid().ToString('N'))"
    try {
        $sw = [Diagnostics.Stopwatch]::StartNew()
        $dom = @(& $Browser '--headless=new' "--user-data-dir=$profile" '--dump-dom' $check.url 2>&1)
        $exitCode = $LASTEXITCODE
        $sw.Stop()
        $domText = $dom -join [Environment]::NewLine
        $domText | Set-Content -Encoding utf8 (Join-Path $OutputDir "$($check.name).html")
        $rows += [pscustomobject]@{
            url = $check.url
            elapsed_ms = [math]::Round($sw.Elapsed.TotalMilliseconds,3)
            exit_code = $exitCode
            expected_output = $check.expected
            output_matched = $domText -match [regex]::Escape($check.expected)
        }
        if ($exitCode -ne 0) {
            throw "Headless navigation failed for $($check.url) with exit code $exitCode."
        }
        if ($domText -notmatch [regex]::Escape($check.expected)) {
            throw "Headless navigation for $($check.url) did not contain expected output: $($check.expected)"
        }
    } finally {
        Remove-Item -Recurse -Force $profile -ErrorAction SilentlyContinue
    }
}
$rows | Export-Csv -NoTypeInformation -Encoding utf8 (Join-Path $OutputDir 'headless-smoke.csv')

$launcherProcess = Start-Process -FilePath $Launcher -ArgumentList @(
    "--browser=`"$Browser`"",
    "--config-dir=`"$ConfigDir`"",
    '--nautrix-use-config-dir-directly',
    '--benchmark-only',
    '--force-dns-retest'
) -Wait -PassThru
if ($launcherProcess.ExitCode -ne 0) {
    throw "DNS benchmark failed with exit code $($launcherProcess.ExitCode)"
}
$dnsMetrics = Join-Path (Join-Path $env:LOCALAPPDATA 'Nautrix') 'dns-metrics.csv'
if (-not (Test-Path -LiteralPath $dnsMetrics -PathType Leaf)) {
    throw "DNS benchmark returned success without producing metrics: $dnsMetrics"
}
$metricsText = Get-Content -Raw -LiteralPath $dnsMetrics
if ($metricsText -notmatch '(?m)^selected=(?!system\r?$)[^\r\n]+\r?$' -or
    $metricsText -notmatch '(?m)^provider,endpoint,dns_median_ms,') {
    throw "DNS benchmark metrics do not contain a selected provider and score table."
}

Write-Host "[Nautrix] Runtime smoke completed: $OutputDir"
