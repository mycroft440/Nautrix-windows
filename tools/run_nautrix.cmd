@echo off
setlocal EnableExtensions

for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "EXE=%ROOT%\.chromium-work\src\out\Nautrix\chrome.exe"

if not exist "%EXE%" (
  echo [Nautrix] Browser binary not found.
  echo [Nautrix] Build it first with tools\build_chromium.cmd
  exit /b 1
)

start "" "%EXE%" %*
exit /b 0
