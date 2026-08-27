param(
    [Parameter(Mandatory = $true)]
    [string]$PackageDir
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $PackageDir -PathType Container)) {
    throw "Test package directory not found: $PackageDir"
}
$PackageDir = [IO.Path]::GetFullPath($PackageDir)

function ConvertTo-SafePackagePath {
    param([Parameter(Mandatory = $true)][string]$RelativePath)

    if ([string]::IsNullOrWhiteSpace($RelativePath)) {
        throw 'Package path must not be empty.'
    }
    $normalized = $RelativePath -replace '/', '\'
    if ([IO.Path]::IsPathRooted($normalized)) {
        throw "Package path must be relative: $RelativePath"
    }
    foreach ($segment in ($normalized -split '\\')) {
        if ([string]::IsNullOrWhiteSpace($segment) -or $segment -in '.', '..') {
            throw "Package path is not normalized: $RelativePath"
        }
    }

    $root = $PackageDir.TrimEnd('\') + '\'
    $full = [IO.Path]::GetFullPath((Join-Path $PackageDir $normalized))
    if (-not $full.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Package path escapes the package directory: $RelativePath"
    }
    return $full.Substring($root.Length) -replace '\\', '/'
}

function Get-ActualPackageFiles {
    $files = @{}
    foreach ($item in Get-ChildItem -LiteralPath $PackageDir -Recurse -File) {
        $relative = ConvertTo-SafePackagePath -RelativePath $item.FullName.Substring($PackageDir.TrimEnd('\').Length).TrimStart('\')
        if ($files.ContainsKey($relative)) {
            throw "Duplicate package file path: $relative"
        }
        $files[$relative] = $item
    }
    return $files
}

$required = @(
    'NautrixSetup.exe',
    'NautrixLauncher.exe',
    'NautrixNetworkSettings.exe',
    'initial_preferences.json',
    'Install-Nautrix-Test.ps1',
    'Install-Nautrix-Test.cmd',
    'Start-Nautrix.cmd',
    'Verify-Nautrix-TestPackage.ps1',
    'TEST_INSTALL.md',
    'RUNTIME_CHECKLIST.md',
    'package.json',
    'MANIFEST.json',
    'SHA256SUMS.txt',
    'config/dns.ini',
    'config/latency.ini'
)
foreach ($relative in $required) {
    if (-not (Test-Path -LiteralPath (Join-Path $PackageDir $relative) -PathType Leaf)) {
        throw "Test package is missing: $relative"
    }
}

$manifest = Get-Content -LiteralPath (Join-Path $PackageDir 'MANIFEST.json') -Raw | ConvertFrom-Json
if (-not $manifest.files -or @($manifest.files).Count -eq 0) {
    throw 'Package payload manifest is empty.'
}

$payload = @{}
foreach ($entry in @($manifest.files)) {
    $relative = ConvertTo-SafePackagePath -RelativePath $entry.path
    if ($relative -in 'MANIFEST.json', 'SHA256SUMS.txt') {
        throw "Payload manifest must not include self-generated file: $relative"
    }
    if ($payload.ContainsKey($relative)) {
        throw "Duplicate payload manifest entry: $relative"
    }
    if ($entry.bytes -lt 0 -or $entry.sha256 -notmatch '^[A-F0-9]{64}$') {
        throw "Invalid payload manifest entry: $relative"
    }
    $payload[$relative] = $entry
}

$actual = Get-ActualPackageFiles
$expectedFiles = @{}
foreach ($relative in $payload.Keys) { $expectedFiles[$relative] = $true }
$expectedFiles['MANIFEST.json'] = $true
$expectedFiles['SHA256SUMS.txt'] = $true
if ($actual.Count -ne $expectedFiles.Count) {
    throw 'Package contains an unexpected or unmanifested file.'
}
foreach ($relative in $expectedFiles.Keys) {
    if (-not $actual.ContainsKey($relative)) {
        throw "Package is missing manifest-listed file: $relative"
    }
}

foreach ($relative in $payload.Keys) {
    $entry = $payload[$relative]
    $item = $actual[$relative]
    if ($item.Length -ne [int64]$entry.bytes) {
        throw "Size mismatch: $relative"
    }
    if ((Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash -ne $entry.sha256) {
        throw "Checksum mismatch: $relative"
    }
}

$hashes = @{}
foreach ($line in Get-Content -LiteralPath (Join-Path $PackageDir 'SHA256SUMS.txt')) {
    if ($line -notmatch '^(?<hash>[A-F0-9]{64}) \*(?<path>.+)$') {
        throw "Invalid checksum entry: $line"
    }
    $relative = ConvertTo-SafePackagePath -RelativePath $Matches.path
    if ($hashes.ContainsKey($relative)) {
        throw "Duplicate checksum entry: $relative"
    }
    $hashes[$relative] = $Matches.hash
}

$expectedHashes = @{}
foreach ($relative in $payload.Keys) { $expectedHashes[$relative] = $true }
$expectedHashes['MANIFEST.json'] = $true
if ($hashes.Count -ne $expectedHashes.Count) {
    throw 'Checksum manifest has an unexpected or missing entry.'
}
foreach ($relative in $expectedHashes.Keys) {
    if (-not $hashes.ContainsKey($relative)) {
        throw "Checksum manifest is missing: $relative"
    }
    if ((Get-FileHash -LiteralPath $actual[$relative].FullName -Algorithm SHA256).Hash -ne $hashes[$relative]) {
        throw "Checksum mismatch: $relative"
    }
}

$preferences = Get-Content -LiteralPath (Join-Path $PackageDir 'initial_preferences.json') -Raw | ConvertFrom-Json
if (-not $preferences.distribution.do_not_create_any_shortcuts) {
    throw 'Initial preferences must suppress direct Chromium shortcuts.'
}

$runner = Get-Content -LiteralPath (Join-Path $PackageDir 'Start-Nautrix.cmd') -Raw
if ($runner -notmatch 'NautrixLauncher.exe' -or $runner -notmatch '--browser=' -or $runner -notmatch 'INSTALL_DIR') {
    throw 'Test-package runner does not launch the installed browser through NautrixLauncher.exe.'
}

$installer = Get-Content -LiteralPath (Join-Path $PackageDir 'Install-Nautrix-Test.ps1') -Raw
foreach ($token in ('NautrixSetup.exe', 'initial_preferences.json', 'NautrixLauncher.exe', 'CreateShortcut', 'UninstallAfterTest')) {
    if ($installer -notmatch [regex]::Escape($token)) {
        throw "Test-package installer is missing: $token"
    }
}

Write-Host "[Nautrix] Test package verified: $PackageDir"
