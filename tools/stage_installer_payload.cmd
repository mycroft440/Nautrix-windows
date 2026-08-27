@echo off
setlocal EnableExtensions

if "%~1"=="" (
  echo [Nautrix] Usage: stage_installer_payload.cmd ^<Chromium output dir^>
  exit /b 2
)

for %%I in ("%~dp0..") do set "ROOT=%%~fI"
for %%I in ("%~1") do set "OUT=%%~fI"
set "LAUNCHER=%ROOT%\.launcher-build\Release\NautrixLauncher.exe"
set "SETTINGS=%ROOT%\.launcher-build\Release\NautrixNetworkSettings.exe"

for %%F in ("%LAUNCHER%" "%SETTINGS%" "%ROOT%\config\dns.ini" "%ROOT%\config\latency.ini") do (
  if not exist "%%~F" (
    echo [Nautrix] Missing native installer payload: %%~F
    echo [Nautrix] Run tools\build_launcher.cmd before building Chromium.
    exit /b 1
  )
)

if not exist "%OUT%" mkdir "%OUT%"
if errorlevel 1 exit /b 1
if not exist "%OUT%\config" mkdir "%OUT%\config"
if errorlevel 1 exit /b 1

copy /Y "%LAUNCHER%" "%OUT%\NautrixLauncher.exe" >nul
if errorlevel 1 exit /b 1
copy /Y "%SETTINGS%" "%OUT%\NautrixNetworkSettings.exe" >nul
if errorlevel 1 exit /b 1
copy /Y "%ROOT%\config\dns.ini" "%OUT%\config\dns.ini" >nul
if errorlevel 1 exit /b 1
copy /Y "%ROOT%\config\latency.ini" "%OUT%\config\latency.ini" >nul
if errorlevel 1 exit /b 1

echo [Nautrix] Native installer payload staged in %OUT%.
exit /b 0
