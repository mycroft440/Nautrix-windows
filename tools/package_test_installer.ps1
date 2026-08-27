[CmdletBinding()]
param(
    [ValidateSet('baseline', 'pgo')]
    [string]$Variant = 'baseline',
    [string]$ChromiumOutput,
    [string]$LauncherOutput = (Join-Path (Split-Path -Parent $PSScriptRoot) '.launcher-build/Release'),
    [string]$OutputDir
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot

if (-not $ChromiumOutput) {
    $buildName = if ($Variant -eq 'pgo') { 'NautrixPGO' } else { 'Nautrix' }
    $ChromiumOutput = Join-Path $repo ".chromium-work/src/out/$buildName"
}
if (-not $OutputDir) {
    $OutputDir = Join-Path $repo "dist/Nautrix-$Variant-x64-test"
}

$ChromiumOutput = [IO.Path]::GetFullPath($ChromiumOutput)
$LauncherOutput = [IO.Path]::GetFullPath($LauncherOutput)
$OutputDir = [IO.Path]::GetFullPath($OutputDir)

$required = @(
    (Join-Path $ChromiumOutput 'mini_installer.exe'),
    (Join-Path $ChromiumOutput 'chrome.exe'),
    (Join-Path $LauncherOutput 'NautrixLauncher.exe'),
    (Join-Path $LauncherOutput 'NautrixNetworkSettings.exe'),
    (Join-Path $repo 'config/dns.ini'),
    (Join-Path $repo 'config/latency.ini'),
    (Join-Path $repo 'tools/install_test_package.ps1'),
    (Join-Path $repo 'tools/install_test_package.cmd'),
    (Join-Path $repo 'tools/start_installed_nautrix.cmd'),
    (Join-Path $repo 'tools/verify_test_package.ps1'),
    (Join-Path $repo 'docs/TEST_INSTALL.md')
)
foreach ($path in $required) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required package input was not found: $path"
    }
}
if (Test-Path -LiteralPath $OutputDir) {
    throw "Refusing to overwrite an existing package directory: $OutputDir"
}

New-Item -ItemType Directory -Path $OutputDir | Out-Null
Copy-Item -LiteralPath (Join-Path $ChromiumOutput 'mini_installer.exe') -Destination (Join-Path $OutputDir 'NautrixSetup.exe')
Copy-Item -LiteralPath (Join-Path $LauncherOutput 'NautrixLauncher.exe') -Destination $OutputDir
Copy-Item -LiteralPath (Join-Path $LauncherOutput 'NautrixNetworkSettings.exe') -Destination $OutputDir
Copy-Item -LiteralPath (Join-Path $repo 'tools/install_test_package.ps1') -Destination (Join-Path $OutputDir 'Install-Nautrix-Test.ps1')
Copy-Item -LiteralPath (Join-Path $repo 'tools/install_test_package.cmd') -Destination (Join-Path $OutputDir 'Install-Nautrix-Test.cmd')
Copy-Item -LiteralPath (Join-Path $repo 'tools/start_installed_nautrix.cmd') -Destination (Join-Path $OutputDir 'Start-Nautrix.cmd')
Copy-Item -LiteralPath (Join-Path $repo 'tools/verify_test_package.ps1') -Destination (Join-Path $OutputDir 'Verify-Nautrix-TestPackage.ps1')
Copy-Item -LiteralPath (Join-Path $repo 'docs/TEST_INSTALL.md') -Destination $OutputDir
Copy-Item -LiteralPath (Join-Path $repo 'docs/RUNTIME_CHECKLIST.md') -Destination $OutputDir
Copy-Item -Recurse -LiteralPath (Join-Path $repo 'config') -Destination (Join-Path $OutputDir 'config')

$version = (Get-Content -LiteralPath (Join-Path $repo 'chromium/VERSION') -Raw).Trim()
$metadata = [ordered]@{
    format = 'Nautrix Windows native-installer test package'
    variant = $Variant
    architecture = 'x64'
    chromium_version = $version
    installer = 'NautrixSetup.exe'
    install_command = 'NautrixSetup.exe'
    automated_install_test = 'Install-Nautrix-Test.cmd'
    verifier = 'Verify-Nautrix-TestPackage.ps1'
    launcher = 'Start-Nautrix.cmd'
}
$metadata | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $OutputDir 'package.json') -Encoding utf8

$payloadFiles = @(Get-ChildItem -LiteralPath $OutputDir -Recurse -File |
    Sort-Object FullName |
    ForEach-Object {
        $relative = $_.FullName.Substring($OutputDir.Length).TrimStart('\') -replace '\\', '/'
        [ordered]@{
            path = $relative
            bytes = $_.Length
            sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
        }
    })
$manifest = [ordered]@{
    format = 'Nautrix native-installer test package payload manifest'
    files = $payloadFiles
}
$manifestPath = Join-Path $OutputDir 'MANIFEST.json'
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifestPath -Encoding utf8

$manifestEntry = [ordered]@{
    path = 'MANIFEST.json'
    bytes = (Get-Item -LiteralPath $manifestPath).Length
    sha256 = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash
}
$hashes = @($payloadFiles + $manifestEntry) |
    ForEach-Object { '{0} *{1}' -f $_.sha256, $_.path }
$hashes | Set-Content -LiteralPath (Join-Path $OutputDir 'SHA256SUMS.txt') -Encoding ascii

Write-Host "[Nautrix] Native-installer test package created: $OutputDir"
