param(
    [string]$LauncherOutput = (Join-Path (Split-Path -Parent $PSScriptRoot) '.launcher-build/Release')
)

$ErrorActionPreference = 'Stop'
$files = @('NautrixLauncher.exe', 'NautrixNetworkSettings.exe') | ForEach-Object {
    $path = Join-Path $LauncherOutput $_
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Native helper not found: $path"
    }
    Get-Item -LiteralPath $path
}

$rows = $files | ForEach-Object {
    [PSCustomObject]@{
        file = $_.Name
        bytes = $_.Length
        kib = [math]::Round($_.Length / 1KB, 1)
    }
}
$rows | Format-Table -AutoSize
Write-Host "[Nautrix] Total native-helper size: $(($files | Measure-Object Length -Sum).Sum) bytes"
