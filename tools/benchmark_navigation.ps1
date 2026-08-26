param(
    [Parameter(Mandatory=$true)][string]$Browser,
    [string[]]$Urls = @('https://example.com','https://www.google.com','https://www.mexc.com'),
    [int]$Runs = 3,
    [string]$Output = "$env:LOCALAPPDATA\Nautrix\navigation-benchmark.csv"
)

$ErrorActionPreference = 'Stop'
if (!(Test-Path $Browser)) { throw "Browser not found: $Browser" }
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Output) | Out-Null
"run,url,elapsed_ms,exit_code" | Set-Content -Encoding utf8 $Output

for ($r = 1; $r -le $Runs; $r++) {
    foreach ($url in $Urls) {
        $profile = Join-Path $env:TEMP "nautrix-bench-$PID-$r-$([guid]::NewGuid().ToString('N'))"
        $sw = [Diagnostics.Stopwatch]::StartNew()
        $p = Start-Process -FilePath $Browser -ArgumentList @('--headless=new','--disable-gpu',"--user-data-dir=$profile",'--dump-dom',$url) -NoNewWindow -PassThru -Wait
        $sw.Stop()
        "$r,$url,$([math]::Round($sw.Elapsed.TotalMilliseconds,3)),$($p.ExitCode)" | Add-Content -Encoding utf8 $Output
        Remove-Item -Recurse -Force $profile -ErrorAction SilentlyContinue
    }
}
Write-Host "[Nautrix] Navigation benchmark: $Output"
