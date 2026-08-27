[CmdletBinding()]
param(
    [string]$OutputDir = (Join-Path (Split-Path -Parent $PSScriptRoot) 'dist/fallback'),
    [string]$WorkDir = (Join-Path $env:TEMP 'nautrix-fallback-build')
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$OutputDir = [IO.Path]::GetFullPath($OutputDir)
$WorkDir = [IO.Path]::GetFullPath($WorkDir)

function Read-NautrixVersion {
    $values = @{}
    foreach ($line in Get-Content -LiteralPath (Join-Path $repo 'chromium/VERSION')) {
        $key, $value = $line -split '=', 2
        if ($key -and $value) { $values[$key.Trim()] = $value.Trim() }
    }
    foreach ($required in 'VERSION','MAIN_BRANCH_POSITION') {
        if (-not $values[$required]) { throw "chromium/VERSION is missing $required" }
    }
    return $values
}

function Get-ChromiumSnapshot {
    param(
        [Parameter(Mandatory = $true)][int64]$TargetPosition,
        [Parameter(Mandatory = $true)][string]$ZipPath
    )

    $bucket = 'https://commondatastorage.googleapis.com/chromium-browser-snapshots/Win_x64'
    $latestText = (Invoke-WebRequest -Uri "$bucket/LAST_CHANGE" -UseBasicParsing).Content.Trim()
    $latestPosition = [int64]$latestText
    $candidates = [System.Collections.Generic.List[int64]]::new()
    $candidates.Add($TargetPosition)
    if ($latestPosition -ne $TargetPosition) { $candidates.Add($latestPosition) }

    foreach ($position in $candidates) {
        $uri = "$bucket/$position/chrome-win.zip"
        try {
            if (Test-Path -LiteralPath $ZipPath) { Remove-Item -LiteralPath $ZipPath -Force }
            Write-Host "[Nautrix] Downloading official Chromium Win_x64 snapshot $position..."
            Invoke-WebRequest -Uri $uri -OutFile $ZipPath -UseBasicParsing
            if ((Get-Item -LiteralPath $ZipPath).Length -lt 1MB) {
                throw "Downloaded snapshot archive is unexpectedly small."
            }
            return [PSCustomObject]@{
                Position = $position
                Uri = $uri
                LatestPosition = $latestPosition
            }
        } catch {
            Write-Warning "Chromium snapshot $position was unavailable: $($_.Exception.Message)"
        }
    }
    throw "Could not download the pinned Chromium snapshot or the current official Win_x64 snapshot."
}

$versionInfo = Read-NautrixVersion
$targetVersion = $versionInfo.VERSION
$targetPosition = [int64]$versionInfo.MAIN_BRANCH_POSITION

$launcherDir = Join-Path $repo '.launcher-build/Release'
$requiredHelpers = @(
    (Join-Path $launcherDir 'NautrixLauncher.exe'),
    (Join-Path $launcherDir 'NautrixNetworkSettings.exe')
)
foreach ($helper in $requiredHelpers) {
    if (-not (Test-Path -LiteralPath $helper -PathType Leaf)) {
        throw "Native Nautrix helper was not built: $helper"
    }
}

if (Test-Path -LiteralPath $WorkDir) { Remove-Item -LiteralPath $WorkDir -Recurse -Force }
if (Test-Path -LiteralPath $OutputDir) { Remove-Item -LiteralPath $OutputDir -Recurse -Force }
New-Item -ItemType Directory -Path $WorkDir, $OutputDir | Out-Null

$zip = Join-Path $WorkDir 'chrome-win.zip'
$snapshot = Get-ChromiumSnapshot -TargetPosition $targetPosition -ZipPath $zip
$extract = Join-Path $WorkDir 'extract'
Expand-Archive -LiteralPath $zip -DestinationPath $extract

$browser = Get-ChildItem -LiteralPath $extract -Filter chrome.exe -Recurse -File |
    Where-Object { $_.Directory.Name -like 'chrome-win*' } |
    Select-Object -First 1
if (-not $browser) { throw 'The official Chromium snapshot did not contain chrome.exe.' }
$chromeDir = $browser.Directory.FullName

$payload = Join-Path $WorkDir 'payload'
New-Item -ItemType Directory -Path $payload | Out-Null
Copy-Item -LiteralPath (Join-Path $chromeDir '*') -Destination $payload -Recurse -Force
Copy-Item -LiteralPath (Join-Path $launcherDir 'NautrixLauncher.exe') -Destination $payload -Force
Copy-Item -LiteralPath (Join-Path $launcherDir 'NautrixNetworkSettings.exe') -Destination $payload -Force
Copy-Item -LiteralPath (Join-Path $repo 'config') -Destination $payload -Recurse -Force

$notice = @"
NAUTRIX WINDOWS FALLBACK BUILD

This installer exists so Nautrix can be installed and exercised while the dedicated
full-Chromium build runner is unavailable. The browser engine in this package is an
official precompiled Chromium Win_x64 snapshot from chromium-browser-snapshots.

Included Nautrix components:
- NautrixLauncher.exe
- NautrixNetworkSettings.exe
- DNS/latency configuration
- per-user Windows shortcuts, browser capabilities and uninstall registration

Important: source-level Nautrix Chromium patches are NOT present in this fallback
engine. The definitive low-latency release is produced by the Full Chromium Build
workflow from the pinned Nautrix Chromium source.

Target source version: $targetVersion
Target branch position: $targetPosition
Fallback snapshot position: $($snapshot.Position)
"@
$notice | Set-Content -LiteralPath (Join-Path $payload 'FALLBACK-NOTICE.txt') -Encoding utf8

$actualBrowserVersion = (& (Join-Path $payload 'chrome.exe') --version 2>&1 | Out-String).Trim()
if (-not $actualBrowserVersion) { throw 'Could not read the fallback Chromium browser version.' }
Write-Host "[Nautrix] Fallback browser: $actualBrowserVersion"

$makensis = Get-Command makensis.exe -ErrorAction SilentlyContinue
if (-not $makensis) { $makensis = Get-Command makensis -ErrorAction SilentlyContinue }
if (-not $makensis) {
    $known = @(
        (Join-Path ${env:ProgramFiles(x86)} 'NSIS/makensis.exe'),
        (Join-Path $env:ProgramFiles 'NSIS/makensis.exe')
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) | Select-Object -First 1
    if (-not $known) { throw 'makensis.exe was not found. Install NSIS before building the fallback installer.' }
    $makensisPath = $known
} else {
    $makensisPath = $makensis.Source
}

$setup = Join-Path $OutputDir 'NautrixFallbackSetup.exe'
$nsi = Join-Path $repo 'installer/fallback/NautrixFallback.nsi'
& $makensisPath "/DPAYLOAD_DIR=$payload" "/DOUTPUT_FILE=$setup" "/DVERSION=$targetVersion" $nsi
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $setup -PathType Leaf)) {
    throw "NSIS failed to produce the fallback installer. Exit code: $LASTEXITCODE"
}

$metadata = [ordered]@{
    format = 'Nautrix Windows fallback installer'
    definitive_release = $false
    target_chromium_version = $targetVersion
    target_main_branch_position = $targetPosition
    snapshot_position = $snapshot.Position
    snapshot_url = $snapshot.Uri
    official_latest_snapshot_position = $snapshot.LatestPosition
    browser_version = $actualBrowserVersion
    architecture = 'x64'
    installer = 'NautrixFallbackSetup.exe'
}
$metadata | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $OutputDir 'fallback-build.json') -Encoding utf8
Copy-Item -LiteralPath (Join-Path $payload 'FALLBACK-NOTICE.txt') -Destination $OutputDir

$hashLines = foreach ($file in Get-ChildItem -LiteralPath $OutputDir -File | Sort-Object Name) {
    if ($file.Name -eq 'SHA256SUMS.txt') { continue }
    '{0} *{1}' -f (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash, $file.Name
}
$hashLines | Set-Content -LiteralPath (Join-Path $OutputDir 'SHA256SUMS.txt') -Encoding ascii

Write-Host "[Nautrix] Fallback installer created: $setup"
