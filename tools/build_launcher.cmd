@echo off
setlocal EnableExtensions

for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "BUILD=%ROOT%\.launcher-build"

cmake -S "%ROOT%\launcher" -B "%BUILD%" -A x64
if errorlevel 1 exit /b 1

cmake --build "%BUILD%" --config Release --parallel
if errorlevel 1 exit /b 1

if not exist "%BUILD%\Release\NautrixLauncher.exe" (
  echo [Nautrix] Launcher build completed but NautrixLauncher.exe was not found.
  exit /b 1
)

echo [Nautrix] Launcher built: %BUILD%\Release\NautrixLauncher.exe
exit /b 0
