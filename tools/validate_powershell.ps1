$ErrorActionPreference = 'Stop'
$failed = $false
Get-ChildItem -Path (Join-Path $PSScriptRoot '*.ps1') | ForEach-Object {
    $tokens = $null
    $errors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($_.FullName, [ref]$tokens, [ref]$errors)
    if ($errors.Count -gt 0) {
        $failed = $true
        Write-Error "PowerShell parse error in $($_.Name): $($errors | ForEach-Object Message | Out-String)"
    }
}
if ($failed) { exit 1 }
Write-Host '[Nautrix] PowerShell tooling parsed successfully.'
