@echo off
setlocal
cd /d "%~dp0"
echo [Nautrix] Starting self-hosted runner setup...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\setup_nautrix_runner.ps1"
set "EXITCODE=%ERRORLEVEL%"
echo.
if not "%EXITCODE%"=="0" (
  echo [Nautrix] Runner setup failed with exit code %EXITCODE%.
) else (
  echo [Nautrix] Runner setup finished.
)
pause
exit /b %EXITCODE%
