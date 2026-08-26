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

$version = & $Browser --version
$version | Set-Content -Encoding utf8 (Join-Path $OutputDir 'version.txt')

$urls = @('https://example.com','https://www.google.com')
$rows = @()
foreach ($url in $urls) {
    $profile = Join-Path $env:TEMP "nautrix-smoke-$PID-$([guid]::NewGuid().ToString('N'))"
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $p = Start-Process -FilePath $Browser -ArgumentList @('--headless=new',"--user-data-dir=$profile",'--dump-dom',$url) -NoNewWindow -Wait -PassThru
    $sw.Stop()
    $rows += [pscustomobject]@{ url=$url; elapsed_ms=[math]::Round($sw.Elapsed.TotalMilliseconds,3); exit_code=$p.ExitCode }
    Remove-Item -Recurse -Force $profile -ErrorAction SilentlyContinue
}
$rows | Export-Csv -NoTypeInformation -Encoding utf8 (Join-Path $OutputDir 'headless-smoke.csv')

& $Launcher --browser="$Browser" --config-dir="$ConfigDir" --benchmark-only --force-dns-retest
if ($LASTEXITCODE -ne 0) { throw "DNS benchmark failed with exit code $LASTEXITCODE" }

Write-Host "[Nautrix] Runtime smoke completed: $OutputDir"
