param(
    [string]$Output = "$env:LOCALAPPDATA\Nautrix\runtime-processes.csv",
    [int]$Seconds = 30,
    [int]$IntervalMs = 500
)

$ErrorActionPreference = 'Stop'
$directory = Split-Path -Parent $Output
New-Item -ItemType Directory -Force -Path $directory | Out-Null
"timestamp,pid,cpu_seconds,working_set_mb,private_mb,threads" | Set-Content -Encoding utf8 $Output

$deadline = (Get-Date).AddSeconds($Seconds)
while ((Get-Date) -lt $deadline) {
    $stamp = (Get-Date).ToString('o')
    Get-Process chrome -ErrorAction SilentlyContinue | ForEach-Object {
        $private = if ($_.PrivateMemorySize64) { $_.PrivateMemorySize64 / 1MB } else { 0 }
        "$stamp,$($_.Id),$([math]::Round($_.CPU,3)),$([math]::Round($_.WorkingSet64/1MB,3)),$([math]::Round($private,3)),$($_.Threads.Count)" | Add-Content -Encoding utf8 $Output
    }
    Start-Sleep -Milliseconds $IntervalMs
}
Write-Host "[Nautrix] Process profile: $Output"
