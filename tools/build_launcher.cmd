@echo off
setlocal EnableExtensions

for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "BUILD=%ROOT%\.launcher-build"
set "CMAKE=cmake"

where cmake >nul 2>&1
if errorlevel 1 (
  set "CMAKE="
  for /f "delims=" %%I in ('where /r "%ProgramFiles%\Microsoft Visual Studio" cmake.exe 2^>nul') do set "CMAKE=%%I"
)
if not defined CMAKE (
  echo [Nautrix] CMake was not found. Install Visual Studio C++ tools or add CMake to PATH.
  exit /b 1
)

"%CMAKE%" -S "%ROOT%\launcher" -B "%BUILD%" -A x64
if errorlevel 1 exit /b 1

"%CMAKE%" --build "%BUILD%" --config Release --parallel
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
