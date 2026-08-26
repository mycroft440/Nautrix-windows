param(
    [string]$WebView2Version = "1.0.4129.50"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$packagesDir = Join-Path $repoRoot "packages"
$packageDir = Join-Path $packagesDir "Microsoft.Web.WebView2.$WebView2Version"
$headerPath = Join-Path $packageDir "build\native\include\WebView2.h"

if (Test-Path $headerPath) {
    Write-Host "WebView2 SDK $WebView2Version is already available."
    exit 0
}

New-Item -ItemType Directory -Force -Path $packagesDir | Out-Null
$tempPackage = Join-Path ([System.IO.Path]::GetTempPath()) "Microsoft.Web.WebView2.$WebView2Version.nupkg"

try {
    $uri = "https://www.nuget.org/api/v2/package/Microsoft.Web.WebView2/$WebView2Version"
    Write-Host "Downloading Microsoft.Web.WebView2 $WebView2Version..."
    Invoke-WebRequest -Uri $uri -OutFile $tempPackage -UseBasicParsing

    if (Test-Path $packageDir) {
        Remove-Item -Recurse -Force $packageDir
    }

    Expand-Archive -Path $tempPackage -DestinationPath $packageDir -Force

    if (-not (Test-Path $headerPath)) {
        throw "WebView2 SDK extraction completed, but WebView2.h was not found."
    }

    Write-Host "WebView2 SDK installed at $packageDir"
}
finally {
    if (Test-Path $tempPackage) {
        Remove-Item -Force $tempPackage
    }
}
