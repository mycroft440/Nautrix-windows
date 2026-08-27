param(
    [Parameter(Mandatory=$true)][string]$Browser,
    [int]$Seconds = 30,
    [string[]]$Urls = @(
        'https://example.com',
        'https://www.mexc.com',
        'https://www.tradingview.com'
    ),
    [string]$Output = "$env:LOCALAPPDATA\Nautrix\runtime-processes.csv"
)

$ErrorActionPreference = 'Stop'
if (!(Test-Path $Browser)) { throw "Browser not found: $Browser" }
$Browser = [IO.Path]::GetFullPath($Browser)
$profile = Join-Path $env:TEMP "nautrix-profile-$PID-$([guid]::NewGuid().ToString('N'))"
$args = [System.Collections.Generic.List[string]]::new()
$args.Add('--headless=new')
$args.Add("--user-data-dir=$profile")
$args.Add('--remote-debugging-port=0')
foreach ($url in $Urls) { $args.Add($url) }

$p = Start-Process -FilePath $Browser -ArgumentList @($args) -PassThru
try {
    Start-Sleep -Seconds 5
    & (Join-Path $PSScriptRoot 'profile_runtime.ps1') -Browser $Browser -Seconds $Seconds -Output $Output
} finally {
    & taskkill.exe /PID $p.Id /T /F 2>$null | Out-Null
    Remove-Item -Recurse -Force $profile -ErrorAction SilentlyContinue
}
Write-Host "[Nautrix] Browser process profile completed: $Output"
