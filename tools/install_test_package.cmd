@echo off
setlocal EnableExtensions

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Verify-Nautrix-TestPackage.ps1" -PackageDir "%~dp0"
if errorlevel 1 exit /b %ERRORLEVEL%

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-Nautrix-Test.ps1" -PackageDir "%~dp0"
exit /b %ERRORLEVEL%
