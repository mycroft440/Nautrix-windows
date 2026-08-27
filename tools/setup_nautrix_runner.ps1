#Requires -Version 5.1

[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Repository = 'mycroft440/Nautrix-windows'
$RepositoryUrl = "https://github.com/$Repository"
$RunnerLabel = 'nautrix-chromium'
$RunnerName = "$env:COMPUTERNAME-nautrix"
$MinimumFreeBytes = 100GB
$RecommendedFreeBytes = 180GB

function Write-Step([string]$Message) {
    Write-Host "`n[Nautrix] $Message" -ForegroundColor Cyan
}

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Refresh-Path {
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machine;$user"
}

function Require-Winget {
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw 'winget.exe was not found. Install Microsoft App Installer from the Microsoft Store, then run this installer again.'
    }
    return $winget.Source
}

function Install-WingetPackage([string]$Id, [string]$DisplayName, [string[]]$ExtraArgs = @()) {
    Write-Step "Installing $DisplayName..."
    $winget = Require-Winget
    $args = @(
        'install', '--id', $Id, '--exact',
        '--accept-package-agreements', '--accept-source-agreements',
        '--disable-interactivity'
    ) + $ExtraArgs
    & $winget @args
    if ($LASTEXITCODE -ne 0) {
        throw "$DisplayName installation failed with exit code $LASTEXITCODE."
    }
    Refresh-Path
}

function Ensure-Git {
    if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) {
        Install-WingetPackage 'Git.Git' 'Git' @('--silent')
    }
    $git = Get-Command git.exe -ErrorAction Stop
    Write-Host "[Nautrix] Git: $($git.Source)"
}

function Enable-LongPathSupport {
    Write-Step 'Enabling Windows/Git long-path support required by Chromium...'
    New-ItemProperty `
        -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' `
        -Name 'LongPathsEnabled' `
        -PropertyType DWord `
        -Value 1 `
        -Force | Out-Null
    & git.exe config --system core.longpaths true
    if ($LASTEXITCODE -ne 0) {
        throw 'Could not enable Git long-path support.'
    }
    Write-Host '[Nautrix] Long-path support: enabled'
}

function Ensure-GitHubCli {
    if (-not (Get-Command gh.exe -ErrorAction SilentlyContinue)) {
        Install-WingetPackage 'GitHub.cli' 'GitHub CLI' @('--silent')
    }
    $gh = Get-Command gh.exe -ErrorAction Stop
    Write-Host "[Nautrix] GitHub CLI: $($gh.Source)"
    return $gh.Source
}

function Get-VsWherePath {
    $candidate = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (Test-Path -LiteralPath $candidate) { return $candidate }
    return $null
}

function Test-CppBuildTools {
    $vswhere = Get-VsWherePath
    if (-not $vswhere) { return $false }
    $path = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    return -not [string]::IsNullOrWhiteSpace(($path | Select-Object -First 1))
}

function Ensure-CppBuildTools {
    if (Test-CppBuildTools) {
        Write-Host '[Nautrix] Visual Studio C++ build tools: ready'
        return
    }

    Write-Step 'Visual Studio 2022 C++ Build Tools are missing. Installing the required native toolchain...'
    Write-Host '[Nautrix] This is a large install and can take several minutes.' -ForegroundColor Yellow
    Install-WingetPackage 'Microsoft.VisualStudio.2022.BuildTools' 'Visual Studio 2022 Build Tools' @(
        '--override', '--wait --passive --norestart --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended'
    )

    if (-not (Test-CppBuildTools)) {
        throw 'Visual Studio C++ build tools were not detected after installation.'
    }
    Write-Host '[Nautrix] Visual Studio C++ build tools: ready'
}

function Select-RunnerDrive {
    $drives = Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' |
        Where-Object { $_.FreeSpace -ge $MinimumFreeBytes } |
        Sort-Object FreeSpace -Descending

    if (-not $drives) {
        $all = Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' |
            Sort-Object FreeSpace -Descending
        $summary = ($all | ForEach-Object { '{0}: {1:N1} GB free' -f $_.DeviceID, ($_.FreeSpace / 1GB) }) -join ', '
        throw "Chromium needs substantial disk space. No fixed drive has at least 100 GB free. Current drives: $summary"
    }

    $system = $drives | Where-Object { $_.DeviceID -eq $env:SystemDrive } | Select-Object -First 1
    $selected = if ($system -and $system.FreeSpace -ge $RecommendedFreeBytes) { $system } else { $drives | Select-Object -First 1 }

    $freeGb = [math]::Round($selected.FreeSpace / 1GB, 1)
    Write-Host "[Nautrix] Runner drive: $($selected.DeviceID) ($freeGb GB free)"
    if ($selected.FreeSpace -lt $RecommendedFreeBytes) {
        Write-Warning 'Less than 180 GB is free. The build may still work, but 180+ GB is recommended for checkout + outputs.'
    }
    return $selected.DeviceID
}

function Ensure-GitHubAuthentication([string]$Gh) {
    Write-Step 'Checking GitHub authentication...'
    & $Gh auth status --hostname github.com *> $null
    if ($LASTEXITCODE -eq 0) {
        Write-Host '[Nautrix] GitHub CLI is authenticated.'
        return
    }

    Write-Host '[Nautrix] A browser window will open once so you can authorize GitHub CLI.' -ForegroundColor Yellow
    & $Gh auth login --hostname github.com --git-protocol https --web
    if ($LASTEXITCODE -ne 0) {
        throw 'GitHub CLI authentication was not completed.'
    }

    & $Gh auth status --hostname github.com *> $null
    if ($LASTEXITCODE -ne 0) {
        throw 'GitHub CLI is still not authenticated.'
    }
}

function Get-RegistrationToken([string]$Gh) {
    Write-Step 'Requesting a short-lived self-hosted runner registration token...'
    $json = & $Gh api --method POST "repos/$Repository/actions/runners/registration-token"
    if ($LASTEXITCODE -ne 0) {
        throw 'Could not create a runner registration token. The authenticated GitHub account must have repository administration access.'
    }
    $parsed = $json | ConvertFrom-Json
    if ([string]::IsNullOrWhiteSpace($parsed.token)) {
        throw 'GitHub returned an empty runner registration token.'
    }
    return $parsed.token
}

function Get-RunnerArchive([string]$Destination) {
    Write-Step 'Resolving the latest official GitHub Actions Runner for Windows x64...'
    $headers = @{ 'User-Agent' = 'Nautrix-Runner-Bootstrap' }
    $release = Invoke-RestMethod -Headers $headers -Uri 'https://api.github.com/repos/actions/runner/releases/latest'
    $asset = $release.assets | Where-Object { $_.name -match '^actions-runner-win-x64-.*\.zip$' } | Select-Object -First 1
    if (-not $asset) {
        throw 'Could not find the Windows x64 actions-runner asset in the latest GitHub release.'
    }

    $archive = Join-Path $Destination $asset.name
    Write-Host "[Nautrix] Runner version: $($release.tag_name)"
    Invoke-WebRequest -Headers $headers -Uri $asset.browser_download_url -OutFile $archive
    return $archive
}

function Wait-RunnerOnline([string]$Gh) {
    Write-Step "Waiting for runner '$RunnerName' to become online in GitHub..."
    for ($attempt = 1; $attempt -le 30; $attempt++) {
        $json = & $Gh api "repos/$Repository/actions/runners?per_page=100" 2>$null
        if ($LASTEXITCODE -eq 0 -and $json) {
            $payload = $json | ConvertFrom-Json
            $runner = $payload.runners |
                Where-Object { $_.name -eq $RunnerName } |
                Select-Object -First 1
            if ($runner) {
                $labels = @($runner.labels | ForEach-Object { $_.name })
                if ($runner.status -eq 'online' -and $labels -contains $RunnerLabel) {
                    Write-Host "[Nautrix] Runner is online: $RunnerName"
                    return
                }
            }
        }
        Start-Sleep -Seconds 2
    }
    throw "The runner service was started, but GitHub did not report '$RunnerName' online with label '$RunnerLabel' within 60 seconds."
}

function Get-RunnerServiceName([string]$Root) {
    $serviceConfig = Join-Path $Root '.service'
    if (-not (Test-Path -LiteralPath $serviceConfig)) {
        return $null
    }

    $serviceName = (Get-Content -Raw -LiteralPath $serviceConfig).Trim()
    if ([string]::IsNullOrWhiteSpace($serviceName)) {
        return $null
    }
    return $serviceName
}

function Start-RunnerWindowsService([string]$Root) {
    # Modern Windows runners configured with --runasservice manage the service directly.
    # Do not depend on svc.cmd; the runner stores the Windows service name in .service.
    $serviceName = Get-RunnerServiceName $Root
    if ([string]::IsNullOrWhiteSpace($serviceName)) {
        return $false
    }

    $service = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
    if (-not $service) {
        Write-Warning "Runner service '$serviceName' is recorded in .service but is not installed."
        return $false
    }

    if ($service.Status -ne [System.ServiceProcess.ServiceControllerStatus]::Running) {
        Write-Step "Starting the GitHub Actions Runner Windows service '$serviceName'..."
        Start-Service -Name $serviceName
        $service.WaitForStatus([System.ServiceProcess.ServiceControllerStatus]::Running, [TimeSpan]::FromSeconds(30))
        $service.Refresh()
    }

    Write-Host "[Nautrix] Runner Windows service: $serviceName ($($service.Status))"
    return $service.Status -eq [System.ServiceProcess.ServiceControllerStatus]::Running
}

function Remove-StaleRunnerWindowsService([string]$Root) {
    $serviceName = Get-RunnerServiceName $Root
    if ([string]::IsNullOrWhiteSpace($serviceName)) {
        return
    }

    $service = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
    if (-not $service) {
        return
    }

    Write-Step "Removing stale runner Windows service '$serviceName' before repair..."
    if ($service.Status -ne [System.ServiceProcess.ServiceControllerStatus]::Stopped) {
        Stop-Service -Name $serviceName -Force -ErrorAction SilentlyContinue
        try {
            $service.WaitForStatus([System.ServiceProcess.ServiceControllerStatus]::Stopped, [TimeSpan]::FromSeconds(20))
        } catch {
            Write-Warning "Runner service '$serviceName' did not report Stopped before deletion; continuing repair."
        }
    }

    & sc.exe delete $serviceName | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "Could not remove stale runner service '$serviceName' (sc.exe exit $LASTEXITCODE)."
    }

    for ($attempt = 1; $attempt -le 20; $attempt++) {
        if (-not (Get-Service -Name $serviceName -ErrorAction SilentlyContinue)) {
            return
        }
        Start-Sleep -Milliseconds 500
    }
    throw "Runner service '$serviceName' is still registered after deletion. Reboot Windows and run the installer again."
}

if (-not [Environment]::Is64BitOperatingSystem) {
    throw 'The Nautrix Chromium build requires 64-bit Windows.'
}

if (-not (Test-Administrator)) {
    Write-Host '[Nautrix] Administrator privileges are required. Requesting UAC elevation...' -ForegroundColor Yellow
    $arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList $arguments
    exit 0
}

Write-Host '============================================================' -ForegroundColor DarkCyan
Write-Host ' Nautrix Windows - GitHub Actions runner setup ' -ForegroundColor Cyan
Write-Host '============================================================' -ForegroundColor DarkCyan
Write-Host "Repository : $Repository"
Write-Host "Runner name: $RunnerName"
Write-Host "Build label: $RunnerLabel"

$drive = Select-RunnerDrive
$runnerRoot = Join-Path "$drive\" 'actions-runner\nautrix-chromium'

Ensure-Git
Enable-LongPathSupport
$gh = Ensure-GitHubCli
Ensure-CppBuildTools
Ensure-GitHubAuthentication $gh

if (Test-Path -LiteralPath (Join-Path $runnerRoot '.runner')) {
    Write-Step "An existing runner configuration was found at $runnerRoot. Checking its Windows service..."
    $existingReady = $false
    try {
        $existingReady = Start-RunnerWindowsService $runnerRoot
        if ($existingReady) {
            Wait-RunnerOnline $gh
        }
    } catch {
        Write-Warning "Existing runner could not be resumed: $($_.Exception.Message)"
        $existingReady = $false
    }

    if ($existingReady) {
        Write-Host "`n[Nautrix] Runner is installed and running as a Windows service." -ForegroundColor Green
        Write-Host '[Nautrix] The latest queued Full Chromium Build can now start automatically.' -ForegroundColor Green
        exit 0
    }

    Write-Warning 'The existing runner configuration is incomplete or its Windows service is broken. Nautrix will repair it automatically.'
    Remove-StaleRunnerWindowsService $runnerRoot
}

if (Test-Path -LiteralPath $runnerRoot) {
    Write-Step 'Removing an incomplete previous runner directory...'
    Remove-Item -LiteralPath $runnerRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $runnerRoot -Force | Out-Null

$tempRoot = Join-Path $env:TEMP 'nautrix-runner-bootstrap'
if (Test-Path -LiteralPath $tempRoot) {
    Remove-Item -LiteralPath $tempRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

try {
    $archive = Get-RunnerArchive $tempRoot
    Write-Step "Extracting GitHub Actions Runner to $runnerRoot..."
    Expand-Archive -LiteralPath $archive -DestinationPath $runnerRoot -Force

    $token = Get-RegistrationToken $gh

    Write-Step "Registering runner '$RunnerName' with label '$RunnerLabel'..."
    Push-Location $runnerRoot
    try {
        & .\config.cmd `
            --unattended `
            --replace `
            --url $RepositoryUrl `
            --token $token `
            --name $RunnerName `
            --labels $RunnerLabel `
            --work '_work' `
            --runasservice
        if ($LASTEXITCODE -ne 0) {
            throw "GitHub Actions Runner configuration failed with exit code $LASTEXITCODE."
        }
    } finally {
        Pop-Location
    }

    Write-Step 'Starting the GitHub Actions Runner Windows service if it is not already running...'
    if (-not (Start-RunnerWindowsService $runnerRoot)) {
        throw 'Runner configuration completed, but the Windows service was not created or could not be started.'
    }

    Wait-RunnerOnline $gh
} finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host ''
Write-Host '============================================================' -ForegroundColor DarkGreen
Write-Host ' Nautrix runner is installed and running as a Windows service ' -ForegroundColor Green
Write-Host '============================================================' -ForegroundColor DarkGreen
Write-Host "Runner directory: $runnerRoot"
Write-Host "Required label   : $RunnerLabel"
Write-Host "Repository       : $RepositoryUrl"
Write-Host ''
Write-Host '[Nautrix] The latest queued Full Chromium Build can now start automatically.' -ForegroundColor Green
