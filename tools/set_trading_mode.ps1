param(
    [ValidateSet('automatic','normal','aggressive')]
    [string]$Mode = 'automatic',
    [string]$Config = ''
)

$ErrorActionPreference = 'Stop'
$packagedConfig = Join-Path (Split-Path -Parent $PSScriptRoot) 'config\latency.ini'
if ([string]::IsNullOrWhiteSpace($Config)) {
    $userConfigDir = Join-Path $env:LOCALAPPDATA 'Nautrix\Config'
    New-Item -ItemType Directory -Path $userConfigDir -Force | Out-Null
    $Config = Join-Path $userConfigDir 'latency.ini'
    if (-not (Test-Path -LiteralPath $Config -PathType Leaf)) {
        if (-not (Test-Path -LiteralPath $packagedConfig -PathType Leaf)) {
            throw "Packaged latency defaults not found: $packagedConfig"
        }
        Copy-Item -LiteralPath $packagedConfig -Destination $Config
    }
}
if (-not (Test-Path -LiteralPath $Config -PathType Leaf)) {
    throw "Latency config not found: $Config"
}

$lines = Get-Content -LiteralPath $Config
$updated = $false
$out = foreach ($line in $lines) {
    if ($line -match '^\s*trading_mode\s*=') {
        $updated = $true
        "trading_mode=$Mode"
    } else {
        $line
    }
}
if (!$updated) { $out = @("trading_mode=$Mode") + $out }
$out | Set-Content -LiteralPath $Config -Encoding utf8
Write-Host "[Nautrix] Trading mode set to '$Mode' in '$Config'. It applies on the next Nautrix launch."
