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

    foreach ($processId in Get-NautrixProcessIds -BrowserPath $BrowserPath) {
        Stop-Process -Id $processId -Force -ErrorAction Stop
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

function Get-NautrixShortcuts {
    $roots = @(
        [Environment]::GetFolderPath('DesktopDirectory'),
        (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs')
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Container) }

    $paths = @()
    foreach ($root in $roots) {
        $paths += @(Get-ChildItem -LiteralPath $root -Filter '*.lnk' -File -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.BaseName -like 'Nautrix*' } |
            Select-Object -ExpandProperty FullName)
    }
    return @($paths | Sort-Object -Unique)
}

function Get-NautrixProgIdCommands {
    $roots = @(
        'HKCU:\Software\Classes',
        'HKLM:\Software\Classes',
        'HKLM:\Software\WOW6432Node\Classes'
    )
    $commands = @()
    foreach ($root in $roots) {
        if (-not (Test-Path -LiteralPath $root)) { continue }
        foreach ($progId in Get-ChildItem -LiteralPath $root -ErrorAction SilentlyContinue |
                 Where-Object { $_.PSChildName -like 'NautrixHTM*' }) {
            $commandKey = Join-Path $progId.PSPath 'shell\open\command'
            if (-not (Test-Path -LiteralPath $commandKey)) { continue }
            $value = (Get-Item -LiteralPath $commandKey).GetValue('')
            if ($value) {
                $commands += [PSCustomObject]@{
                    ProgId = $progId.PSChildName
                    Path = $commandKey
                    Command = [string]$value
                }
            }
        }
    }
    return @($commands)
}

function Assert-NoExistingNautrixShellState {
    $shortcuts = @(Get-NautrixShortcuts)
    if ($shortcuts.Count -ne 0) {
        throw "Unexpected Nautrix shortcut before installation: $($shortcuts[0])"
    }
    $commands = @(Get-NautrixProgIdCommands)
    if ($commands.Count -ne 0) {
        throw "Unexpected Nautrix ProgID before installation: $($commands[0].ProgId)"
    }
}

function Assert-InstalledPayload {
    param(
        [Parameter(Mandatory = $true)][string]$Launcher,
        [Parameter(Mandatory = $true)][string]$Settings,
        [Parameter(Mandatory = $true)][string]$Config
    )

    $pairs = @(
        @((Join-Path $PackageDir 'NautrixLauncher.exe'), $Launcher),
        @((Join-Path $PackageDir 'NautrixNetworkSettings.exe'), $Settings),
        @((Join-Path $PackageDir 'config\dns.ini'), (Join-Path $Config 'dns.ini')),
        @((Join-Path $PackageDir 'config\latency.ini'), (Join-Path $Config 'latency.ini'))
    )
    foreach ($pair in $pairs) {
        $source = $pair[0]
        $installed = $pair[1]
        if (-not (Test-Path -LiteralPath $installed -PathType Leaf)) {
            throw "Native installer did not deploy required Nautrix payload: $installed"
        }
        $sourceHash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
        $installedHash = (Get-FileHash -LiteralPath $installed -Algorithm SHA256).Hash
        if ($sourceHash -ne $installedHash) {
            throw "Installed Nautrix payload does not match package payload: $installed"
        }
    }
}

function Assert-NativeShortcuts {
    param([Parameter(Mandatory = $true)][string]$Launcher)

    $shortcuts = @(Get-NautrixShortcuts)
    if ($shortcuts.Count -eq 0) {
        throw 'Native installer did not create a Nautrix Desktop or Start-menu shortcut.'
    }

    $shell = New-Object -ComObject WScript.Shell
    $expectedTarget = [IO.Path]::GetFullPath($Launcher)
    foreach ($path in $shortcuts) {
        $shortcut = $shell.CreateShortcut($path)
        if ([IO.Path]::GetFullPath($shortcut.TargetPath) -ne $expectedTarget) {
            throw "Native Nautrix shortcut bypasses the launcher: $path -> $($shortcut.TargetPath)"
        }
        if ($shortcut.Arguments -notmatch '--browser=' -or
            $shortcut.Arguments -notmatch '--config-dir=') {
            throw "Native Nautrix shortcut is missing launcher routing arguments: $path"
        }
    }
    return $shortcuts
}

function Assert-ProgIdRouting {
    param([Parameter(Mandatory = $true)][string]$Launcher)

    $commands = @(Get-NautrixProgIdCommands)
    if ($commands.Count -eq 0) {
        throw 'Native installer did not register a NautrixHTM browser ProgID.'
    }
    $launcherPattern = [regex]::Escape([IO.Path]::GetFullPath($Launcher))
    foreach ($entry in $commands) {
        if ($entry.Command -notmatch $launcherPattern -or
            $entry.Command -notmatch '--browser=' -or
            $entry.Command -notmatch '--config-dir=' -or
            $entry.Command -notmatch '--single-argument') {
            throw "Nautrix ProgID bypasses launcher routing: $($entry.ProgId) -> $($entry.Command)"
        }
    }
}

function Wait-NautrixUninstalled {
    param(
        [Parameter(Mandatory = $true)][string]$Browser,
        [Parameter(Mandatory = $true)][string]$Launcher,
        [Parameter(Mandatory = $true)][string]$Settings,
        [Parameter(Mandatory = $true)][string]$Config
    )

    for ($attempt = 0; $attempt -lt 30; ++$attempt) {
        $remainingFiles = @($Browser, $Launcher, $Settings, $Config) |
            Where-Object { Test-Path -LiteralPath $_ }
        if (-not (Get-NautrixUninstallEntry) -and
            $remainingFiles.Count -eq 0 -and
            @(Get-NautrixShortcuts).Count -eq 0 -and
            @(Get-NautrixProgIdCommands).Count -eq 0) {
            return
        }
        Start-Sleep -Seconds 1
    }
    throw 'Native Nautrix uninstall left application files, shortcuts, ProgIDs, or uninstall registration behind.'
}

$required = @(
    'NautrixSetup.exe',
    'NautrixLauncher.exe',
    'NautrixNetworkSettings.exe',
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
    Assert-NoExistingNautrixShellState

    # Deliberately run the native setup directly. The test must not copy helper
    # files, inject installerdata, or create shortcuts after installation.
    $setup = Join-Path $PackageDir 'NautrixSetup.exe'
    $setupProcess = Start-Process -FilePath $setup -ArgumentList @(
        '--do-not-launch-chrome'
    ) -Wait -PassThru
    if ($setupProcess.ExitCode -ne 0) {
        throw "NautrixSetup.exe failed with exit code $($setupProcess.ExitCode)."
    }

    $browser = Wait-NautrixBrowser
    $installDir = Split-Path -Parent $browser
    $launcher = Join-Path $installDir 'NautrixLauncher.exe'
    $settings = Join-Path $installDir 'NautrixNetworkSettings.exe'
    $config = Join-Path $installDir 'config'

    Assert-InstalledPayload -Launcher $launcher -Settings $settings -Config $config
    $nativeShortcuts = @(Assert-NativeShortcuts -Launcher $launcher)
    Assert-ProgIdRouting -Launcher $launcher

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
        throw 'The installed Nautrix launcher returned success but no installed browser process was observed.'
    }

    Write-Host "[Nautrix] Standalone native installer validated at: $installDir"
    Write-Host "[Nautrix] Native shortcuts validated: $($nativeShortcuts.Count)"
    Write-Host "[Nautrix] Launcher-routed ProgID registration validated."
} catch {
    $failure = $_
} finally {
    $cleanupFailure = $null
    try {
        $cleanupBrowser = if ($browser) { $browser } else { Get-NautrixBrowserPath }
        if ($cleanupBrowser) { Stop-NautrixProcesses -BrowserPath $cleanupBrowser }

        if ($UninstallAfterTest -and ((Get-NautrixBrowserPath) -or (Get-NautrixUninstallEntry))) {
            Invoke-NautrixUninstall
            $cleanupBrowser = if ($browser) { $browser } else { Join-Path $env:LOCALAPPDATA 'Nautrix/Application/chrome.exe' }
            $cleanupLauncher = if ($launcher) { $launcher } else { Join-Path (Split-Path -Parent $cleanupBrowser) 'NautrixLauncher.exe' }
            $cleanupSettings = if ($settings) { $settings } else { Join-Path (Split-Path -Parent $cleanupBrowser) 'NautrixNetworkSettings.exe' }
            $cleanupConfig = if ($config) { $config } else { Join-Path (Split-Path -Parent $cleanupBrowser) 'config' }
            Wait-NautrixUninstalled -Browser $cleanupBrowser -Launcher $cleanupLauncher -Settings $cleanupSettings -Config $cleanupConfig
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
