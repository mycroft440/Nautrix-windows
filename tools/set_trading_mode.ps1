param(
    [ValidateSet('automatic','normal','aggressive')]
    [string]$Mode = 'automatic',
    [string]$Config = (Join-Path (Split-Path -Parent $PSScriptRoot) 'config\latency.ini')
)

$ErrorActionPreference = 'Stop'
if (!(Test-Path $Config)) { throw "Latency config not found: $Config" }

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
Write-Host "[Nautrix] Trading mode set to '$Mode'. It applies on the next Nautrix launch."
