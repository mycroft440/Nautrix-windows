@echo off
setlocal EnableExtensions

for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "BUILD=%ROOT%\.launcher-build"

cmake -S "%ROOT%\launcher" -B "%BUILD%" -A x64
if errorlevel 1 exit /b 1

cmake --build "%BUILD%" --config Release --parallel
if errorlevel 1 exit /b 1

if not exist "%BUILD%\Release\NautrixLauncher.exe" (
  echo [Nautrix] NautrixLauncher.exe was not produced.
  exit /b 1
)
if not exist "%BUILD%\Release\NautrixNetworkSettings.exe" (
  echo [Nautrix] NautrixNetworkSettings.exe was not produced.
  exit /b 1
)

echo [Nautrix] Native tools built successfully.
exit /b 0
