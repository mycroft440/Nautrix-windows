param(
    [Parameter(Mandatory=$true)][string]$Browser,
    [int]$Seconds = 30,
    [string]$Output = "$env:LOCALAPPDATA\Nautrix\runtime-processes.csv"
)

$ErrorActionPreference = 'Stop'
if (!(Test-Path $Browser)) { throw "Browser not found: $Browser" }
$profile = Join-Path $env:TEMP "nautrix-profile-$PID-$([guid]::NewGuid().ToString('N'))"
$p = Start-Process -FilePath $Browser -ArgumentList @('--headless=new',"--user-data-dir=$profile",'--remote-debugging-port=0','about:blank') -PassThru
try {
    Start-Sleep -Seconds 2
    & (Join-Path $PSScriptRoot 'profile_runtime.ps1') -Seconds $Seconds -Output $Output
} finally {
    & taskkill.exe /PID $p.Id /T /F 2>$null | Out-Null
    Remove-Item -Recurse -Force $profile -ErrorAction SilentlyContinue
}
Write-Host "[Nautrix] Browser process profile completed: $Output"
