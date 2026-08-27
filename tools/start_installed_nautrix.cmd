@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
set "BROWSER="

for %%I in (
  "%LOCALAPPDATA%\Nautrix\Application\chrome.exe"
  "%ProgramFiles%\Nautrix\Application\chrome.exe"
  "%ProgramFiles(x86)%\Nautrix\Application\chrome.exe"
) do (
  if not defined BROWSER if exist "%%~fI" set "BROWSER=%%~fI"
)

if not defined BROWSER (
  echo [Nautrix] Installed browser binary not found.
  echo [Nautrix] Run NautrixSetup.exe from this test package, then try again.
  exit /b 1
)

for %%I in ("%BROWSER%") do set "INSTALL_DIR=%%~dpI"

if not exist "%INSTALL_DIR%\NautrixLauncher.exe" (
  echo [Nautrix] NautrixLauncher.exe is missing from the Nautrix installation.
  exit /b 1
)
if not exist "%INSTALL_DIR%\config\dns.ini" (
  echo [Nautrix] Installed Nautrix configuration is incomplete.
  exit /b 1
)

"%INSTALL_DIR%\NautrixLauncher.exe" --browser="%BROWSER%" --config-dir="%INSTALL_DIR%\config" %*
exit /b %ERRORLEVEL%
