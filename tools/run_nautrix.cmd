@echo off
setlocal EnableExtensions

for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "EXE=%ROOT%\.chromium-work\src\out\Nautrix\chrome.exe"
set "LAUNCHER=%ROOT%\.launcher-build\Release\NautrixLauncher.exe"

if not exist "%EXE%" (
  echo [Nautrix] Browser binary not found.
  echo [Nautrix] Build it first with tools\build_chromium.cmd
  exit /b 1
)
if not exist "%LAUNCHER%" (
  call "%ROOT%\tools\build_launcher.cmd"
  if errorlevel 1 exit /b 1
)

"%LAUNCHER%" --browser="%EXE%" --config-dir="%ROOT%\config" %*
exit /b %ERRORLEVEL%
