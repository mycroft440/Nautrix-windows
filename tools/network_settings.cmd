@echo off
setlocal EnableExtensions
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "SETTINGS=%ROOT%\.launcher-build\Release\NautrixNetworkSettings.exe"
if not exist "%SETTINGS%" (
  call "%ROOT%\tools\build_launcher.cmd"
  if errorlevel 1 exit /b 1
)
start "" "%SETTINGS%" --config-dir="%ROOT%\config"
exit /b 0
