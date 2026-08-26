@echo off
setlocal EnableExtensions
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "BASE=%ROOT%\.chromium-work\src\out\Nautrix\chrome.exe"
set "PGO=%ROOT%\.chromium-work\src\out\NautrixPGO\chrome.exe"
if not exist "%BASE%" (
  echo [Nautrix] Baseline browser not found: %BASE%
  exit /b 1
)
if not exist "%PGO%" (
  echo [Nautrix] PGO browser not found: %PGO%
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\tools\benchmark_pgo.ps1" -BaselineBrowser "%BASE%" -PgoBrowser "%PGO%" -Runs 5
exit /b %ERRORLEVEL%
