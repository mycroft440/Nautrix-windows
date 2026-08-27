[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Setup
)

$ErrorActionPreference = 'Stop'
$Setup = [IO.Path]::GetFullPath($Setup)
if (-not (Test-Path -LiteralPath $Setup -PathType Leaf)) {
    throw "Fallback installer was not found: $Setup"
}

$installDir = Join-Path $env:LOCALAPPDATA 'Nautrix/Application'
$browser = Join-Path $installDir 'chrome.exe'
$launcher = Join-Path $installDir 'NautrixLauncher.exe'
$settings = Join-Path $installDir 'NautrixNetworkSettings.exe'
$config = Join-Path $installDir 'config'
$uninstaller = Join-Path $installDir 'Uninstall.exe'
$desktopShortcut = Join-Path ([Environment]::GetFolderPath('DesktopDirectory')) 'Nautrix.lnk'
$startShortcut = Join-Path $env:APPDATA 'Microsoft/Windows/Start Menu/Programs/Nautrix/Nautrix.lnk'
$progIdKey = 'HKCU:\Software\Classes\NautrixHTM\shell\open\command'
$clientKey = 'HKCU:\Software\Clients\StartMenuInternet\Nautrix\Capabilities'
$uninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\NautrixFallback'

function Get-NautrixProcesses {
    @(Get-Process -Name chrome -ErrorAction SilentlyContinue | Where-Object {
        try { [IO.Path]::GetFullPath($_.Path) -eq [IO.Path]::GetFullPath($browser) } catch { $false }
    })
}

function Stop-NautrixProcesses {
    foreach ($process in Get-NautrixProcesses) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
    for ($attempt = 0; $attempt -lt 20; ++$attempt) {
        if ((Get-NautrixProcesses).Count -eq 0) { return }
        Start-Sleep -Milliseconds 500
    }
    throw 'Installed fallback Chromium processes did not exit.'
}

if (Test-Path -LiteralPath $installDir -PathType Container) {
    throw "A Nautrix installation already exists on this test user: $installDir"
}

$install = Start-Process -FilePath $Setup -ArgumentList '/S' -Wait -PassThru
if ($install.ExitCode -ne 0) { throw "Fallback setup failed with exit code $($install.ExitCode)." }

$required = @(
    $browser,
    $launcher,
    $settings,
    (Join-Path $config 'dns.ini'),
    (Join-Path $config 'latency.ini'),
    (Join-Path $installDir 'FALLBACK-NOTICE.txt'),
    $uninstaller
)
foreach ($path in $required) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Fallback installer did not deploy required file: $path"
    }
}

if (-not (Test-Path -LiteralPath $progIdKey)) { throw 'NautrixHTM shell registration is missing.' }
$shellCommand = (Get-Item -LiteralPath $progIdKey).GetValue('')
if ($shellCommand -notmatch [regex]::Escape('NautrixLauncher.exe') -or
    $shellCommand -notmatch [regex]::Escape('--single-argument') -or
    $shellCommand -notmatch '%1') {
    throw "Unexpected NautrixHTM shell command: $shellCommand"
}

if (-not (Test-Path -LiteralPath $clientKey)) { throw 'Nautrix browser capabilities are missing.' }
if ((Get-ItemPropertyValue -LiteralPath "$clientKey\URLAssociations" -Name 'http') -ne 'NautrixHTM' -or
    (Get-ItemPropertyValue -LiteralPath "$clientKey\URLAssociations" -Name 'https') -ne 'NautrixHTM') {
    throw 'Nautrix HTTP/HTTPS capabilities were not registered.'
}
if ((Get-ItemPropertyValue -LiteralPath 'HKCU:\Software\RegisteredApplications' -Name 'Nautrix') -notmatch 'StartMenuInternet\\Nautrix\\Capabilities') {
    throw 'Nautrix was not registered as a selectable Windows browser application.'
}
if (-not (Test-Path -LiteralPath $uninstallKey)) { throw 'Fallback uninstall registration is missing.' }

$shell = New-Object -ComObject WScript.Shell
foreach ($shortcutPath in @($desktopShortcut, $startShortcut)) {
    if (-not (Test-Path -LiteralPath $shortcutPath -PathType Leaf)) {
        throw "Fallback shortcut is missing: $shortcutPath"
    }
    $shortcut = $shell.CreateShortcut($shortcutPath)
    if ([IO.Path]::GetFullPath($shortcut.TargetPath) -ne [IO.Path]::GetFullPath($launcher)) {
        throw "Fallback shortcut does not route through NautrixLauncher.exe: $shortcutPath"
    }
}

$browserVersionInfo = (Get-Item -LiteralPath $browser).VersionInfo
$version = $browserVersionInfo.ProductVersion
if (-not $version) { $version = $browserVersionInfo.FileVersion }
if (-not $version) { throw 'Installed fallback browser has no PE version metadata.' }
Write-Host "[Nautrix] Installed fallback browser version: $version"

$existingIds = @(Get-NautrixProcesses | Select-Object -ExpandProperty Id)
$launch = Start-Process -FilePath $launcher -ArgumentList @(
    '--headless=new',
    '--remote-debugging-port=0',
    '--no-first-run',
    'about:blank'
) -Wait -PassThru
if ($launch.ExitCode -ne 0) { throw "NautrixLauncher.exe failed with exit code $($launch.ExitCode)." }

$newProcesses = @()
for ($attempt = 0; $attempt -lt 30 -and $newProcesses.Count -eq 0; ++$attempt) {
    Start-Sleep -Seconds 1
    $newProcesses = @(Get-NautrixProcesses | Where-Object { $_.Id -notin $existingIds })
}
if ($newProcesses.Count -eq 0) {
    throw 'NautrixLauncher.exe returned success but no installed Chromium process was observed.'
}
Write-Host "[Nautrix] Launcher started installed Chromium through PID(s): $($newProcesses.Id -join ', ')"
Stop-NautrixProcesses

$uninstall = Start-Process -FilePath $uninstaller -ArgumentList '/S' -Wait -PassThru
if ($uninstall.ExitCode -ne 0) { throw "Fallback uninstaller failed with exit code $($uninstall.ExitCode)." }

for ($attempt = 0; $attempt -lt 30 -and (Test-Path -LiteralPath $installDir); ++$attempt) {
    Start-Sleep -Milliseconds 500
}
if (Test-Path -LiteralPath $installDir) { throw "Fallback uninstall left application files behind: $installDir" }
foreach ($path in @($desktopShortcut, $startShortcut, $progIdKey, $clientKey, $uninstallKey)) {
    if (Test-Path -LiteralPath $path) { throw "Fallback uninstall left registered artifact behind: $path" }
}
if (Get-ItemProperty -LiteralPath 'HKCU:\Software\RegisteredApplications' -Name 'Nautrix' -ErrorAction SilentlyContinue) {
    throw 'Fallback uninstall left Nautrix in RegisteredApplications.'
}

Write-Host '[Nautrix] Fallback install, launch, browser registration, and uninstall lifecycle passed.'
