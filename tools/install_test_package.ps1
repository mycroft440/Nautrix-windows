[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PackageDir,
    [switch]$UninstallAfterTest
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $PackageDir -PathType Container)) {
    throw "Test package directory not found: $PackageDir"
}
$PackageDir = [IO.Path]::GetFullPath($PackageDir)
$verifier = Join-Path $PackageDir 'Verify-Nautrix-TestPackage.ps1'
if (-not (Test-Path -LiteralPath $verifier -PathType Leaf)) {
    throw "Test-package verifier not found: $verifier"
}
& $verifier -PackageDir $PackageDir
if (-not $?) {
    throw 'Test-package verification failed before installation.'
}

function Get-NautrixBrowserPath {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA 'Nautrix/Application/chrome.exe'),
        (Join-Path $env:ProgramFiles 'Nautrix/Application/chrome.exe')
    )
    if (${env:ProgramFiles(x86)}) {
        $candidates += Join-Path ${env:ProgramFiles(x86)} 'Nautrix/Application/chrome.exe'
    }
    return $candidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
}

function Get-NautrixUninstallEntry {
    foreach ($path in @(
        'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Nautrix',
        'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Nautrix'
    )) {
        if (Test-Path -LiteralPath $path) {
            return [PSCustomObject]@{ Path = $path; Values = Get-ItemProperty -LiteralPath $path }
        }
    }
    return $null
}

function Get-NautrixProcessIds {
    param([Parameter(Mandatory = $true)][string]$BrowserPath)
    return @(Get-Process -Name chrome -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -eq $BrowserPath } |
        Select-Object -ExpandProperty Id)
}

function Stop-NautrixProcesses {
    param([Parameter(Mandatory = $true)][string]$BrowserPath)

    foreach ($id in Get-NautrixProcessIds -BrowserPath $BrowserPath) {
        Stop-Process -Id $id -Force -ErrorAction Stop
    }
    for ($attempt = 0; $attempt -lt 15; ++$attempt) {
        if (@(Get-NautrixProcessIds -BrowserPath $BrowserPath).Count -eq 0) { return }
        Start-Sleep -Seconds 1
    }
    throw "Nautrix processes are still running: $BrowserPath"
}

function Wait-NautrixBrowser {
    for ($attempt = 0; $attempt -lt 30; ++$attempt) {
        $browser = Get-NautrixBrowserPath
        if ($browser) { return $browser }
        Start-Sleep -Seconds 1
    }
    throw 'NautrixSetup.exe completed but did not install chrome.exe in a supported location.'
}

function Invoke-NautrixUninstall {
    $entry = Get-NautrixUninstallEntry
    if (-not $entry -or -not $entry.Values.UninstallString) {
        throw 'Nautrix uninstall command was not registered by the installer.'
    }
    $process = Start-Process -FilePath $env:ComSpec -ArgumentList @(
        '/d', '/s', '/c', "$($entry.Values.UninstallString) --force-uninstall"
    ) -Wait -PassThru
    if ($process.ExitCode -notin 0, 19) {
        throw "Nautrix uninstall failed with exit code $($process.ExitCode)."
    }
}

$shortcutPaths = @(
    (Join-Path ([Environment]::GetFolderPath('DesktopDirectory')) 'Nautrix.lnk'),
    (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Nautrix\Nautrix.lnk'),
    (Join-Path $env:APPDATA 'Microsoft\Internet Explorer\Quick Launch\Nautrix.lnk'),
    (Join-Path $env:APPDATA 'Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar\Nautrix.lnk')
)
$createdShortcutPaths = $shortcutPaths[0..1]
$shell = New-Object -ComObject WScript.Shell

function Assert-NoNautrixShortcuts {
    param([Parameter(Mandatory = $true)][string]$Stage)

    foreach ($path in $shortcutPaths) {
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            throw "Unexpected Nautrix shortcut ${Stage}: $path"
        }
    }
}

function Assert-LauncherShortcuts {
    param(
        [Parameter(Mandatory = $true)][string]$Launcher,
        [Parameter(Mandatory = $true)][string]$Arguments
    )

    $expectedTarget = [IO.Path]::GetFullPath($Launcher)
    foreach ($path in $createdShortcutPaths) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Launcher shortcut was not created: $path"
        }
        $shortcut = $shell.CreateShortcut($path)
        if ([IO.Path]::GetFullPath($shortcut.TargetPath) -ne $expectedTarget) {
            throw "Launcher shortcut has an unexpected target: $path"
        }
        if ($shortcut.Arguments -ne $Arguments) {
            throw "Launcher shortcut has unexpected arguments: $path"
        }
    }
}

function Remove-CreatedShortcuts {
    foreach ($path in $createdShortcutPaths) {
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            Remove-Item -LiteralPath $path -Force
        }
    }
}

function Remove-InstalledAuxiliaryPayload {
    param(
        [Parameter(Mandatory = $true)][string]$Launcher,
        [Parameter(Mandatory = $true)][string]$Settings,
        [Parameter(Mandatory = $true)][string]$Config
    )

    # Chromium's native uninstaller does not own the Nautrix files copied in
    # after installation, so the test-package uninstall path must remove them.
    foreach ($path in @($Launcher, $Settings, $Config)) {
        if (Test-Path -LiteralPath $path) {
            Remove-Item -LiteralPath $path -Recurse -Force
        }
    }
}

function Assert-Uninstalled {
    param(
        [Parameter(Mandatory = $true)][string]$Browser,
        [Parameter(Mandatory = $true)][string]$Launcher,
        [Parameter(Mandatory = $true)][string]$Settings,
        [Parameter(Mandatory = $true)][string]$Config
    )

    if (Get-NautrixUninstallEntry) {
        throw 'Nautrix uninstall registry entry remains after uninstall.'
    }
    foreach ($path in @($Browser, $Launcher, $Settings, $Config) + $shortcutPaths) {
        if (Test-Path -LiteralPath $path) {
            throw "Nautrix uninstall left an installed artifact behind: $path"
        }
    }
    Stop-NautrixProcesses -BrowserPath $Browser
}

$required = @(
    'NautrixSetup.exe',
    'NautrixLauncher.exe',
    'NautrixNetworkSettings.exe',
    'initial_preferences.json',
    'config/dns.ini',
    'config/latency.ini'
)
foreach ($relative in $required) {
    if (-not (Test-Path -LiteralPath (Join-Path $PackageDir $relative) -PathType Leaf)) {
        throw "Test package is missing: $relative"
    }
}

$failure = $null
$browser = $null
$launcher = $null
$settings = $null
$config = $null
try {
    if ((Get-NautrixBrowserPath) -or (Get-NautrixUninstallEntry)) {
        throw 'A Nautrix installation already exists. Use a clean Windows test user before running this installation test.'
    }
    Assert-NoNautrixShortcuts -Stage 'before installation'

    $setup = Join-Path $PackageDir 'NautrixSetup.exe'
    $initialPreferences = Join-Path $PackageDir 'initial_preferences.json'
    $setupProcess = Start-Process -FilePath $setup -ArgumentList @(
        "--installerdata=`"$initialPreferences`"",
        '--do-not-launch-chrome'
    ) -Wait -PassThru
    if ($setupProcess.ExitCode -ne 0) {
        throw "NautrixSetup.exe failed with exit code $($setupProcess.ExitCode)."
    }

    $browser = Wait-NautrixBrowser
    Assert-NoNautrixShortcuts -Stage 'after native installation'
    $installDir = Split-Path -Parent $browser
    $launcher = Join-Path $installDir 'NautrixLauncher.exe'
    $settings = Join-Path $installDir 'NautrixNetworkSettings.exe'
    $config = Join-Path $installDir 'config'

    Copy-Item -LiteralPath (Join-Path $PackageDir 'NautrixLauncher.exe') -Destination $launcher
    Copy-Item -LiteralPath (Join-Path $PackageDir 'NautrixNetworkSettings.exe') -Destination $settings
    Copy-Item -Recurse -LiteralPath (Join-Path $PackageDir 'config') -Destination $config

    $shortcutArguments = "--browser=`"$browser`" --config-dir=`"$config`""
    foreach ($path in $createdShortcutPaths) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $path) | Out-Null
        $shortcut = $shell.CreateShortcut($path)
        $shortcut.TargetPath = $launcher
        $shortcut.Arguments = $shortcutArguments
        $shortcut.WorkingDirectory = $installDir
        $shortcut.IconLocation = "$browser,0"
        $shortcut.Save()
    }
    Assert-LauncherShortcuts -Launcher $launcher -Arguments $shortcutArguments

    $existingProcessIds = Get-NautrixProcessIds -BrowserPath $browser
    $launch = Start-Process -FilePath $launcher -ArgumentList @(
        "--browser=`"$browser`"",
        "--config-dir=`"$config`"",
        '--headless=new',
        '--remote-debugging-port=0',
        '--no-first-run',
        'about:blank'
    ) -Wait -PassThru
    if ($launch.ExitCode -ne 0) {
        throw "Nautrix launcher failed after installation with exit code $($launch.ExitCode)."
    }

    $launchedProcessIds = @()
    for ($attempt = 0; $attempt -lt 10 -and $launchedProcessIds.Count -eq 0; ++$attempt) {
        Start-Sleep -Seconds 1
        $launchedProcessIds = @(Get-NautrixProcessIds -BrowserPath $browser | Where-Object { $_ -notin $existingProcessIds })
    }
    if ($launchedProcessIds.Count -eq 0) {
        throw 'The launcher returned success but no installed Nautrix browser process was observed.'
    }

    Write-Host "[Nautrix] Installed browser, launcher, and supported shortcuts validated at: $installDir"
} catch {
    $failure = $_
} finally {
    $cleanupFailure = $null
    try {
        $cleanupBrowser = if ($browser) { $browser } else { Get-NautrixBrowserPath }
        if ($cleanupBrowser) { Stop-NautrixProcesses -BrowserPath $cleanupBrowser }

        if ($UninstallAfterTest -and ((Get-NautrixBrowserPath) -or (Get-NautrixUninstallEntry))) {
            try {
                Invoke-NautrixUninstall
            } finally {
                # These are created by this script only after the clean-user guard passes.
                Remove-CreatedShortcuts
            }
            $cleanupBrowser = if ($browser) { $browser } else { Join-Path $env:LOCALAPPDATA 'Nautrix/Application/chrome.exe' }
            $cleanupLauncher = if ($launcher) { $launcher } else { Join-Path (Split-Path -Parent $cleanupBrowser) 'NautrixLauncher.exe' }
            $cleanupSettings = if ($settings) { $settings } else { Join-Path (Split-Path -Parent $cleanupBrowser) 'NautrixNetworkSettings.exe' }
            $cleanupConfig = if ($config) { $config } else { Join-Path (Split-Path -Parent $cleanupBrowser) 'config' }
            Remove-InstalledAuxiliaryPayload -Launcher $cleanupLauncher -Settings $cleanupSettings -Config $cleanupConfig
            Assert-Uninstalled -Browser $cleanupBrowser -Launcher $cleanupLauncher -Settings $cleanupSettings -Config $cleanupConfig
        }
    } catch {
        $cleanupFailure = $_
    }
    if ($cleanupFailure) {
        if ($failure) {
            [Console]::Error.WriteLine("[Nautrix] Cleanup failure after the primary test error: $($cleanupFailure.Exception.Message)")
        } else {
            $failure = $cleanupFailure
        }
    }
}

if ($failure) { throw $failure }
