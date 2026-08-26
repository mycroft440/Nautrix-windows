@echo off
setlocal EnableExtensions

for %%I in ("%~dp0..") do set "ROOT=%%~fI"

rem Trading mode keeps configured exchange/trading URLs at foreground process
rem priority through the Nautrix Chromium patch, while preserving Chromium's
rem normal timer/background scheduling for unrelated tabs.
call "%ROOT%\tools\run_nautrix.cmd" --enable-features=BrowserProcessAboveNormalPriority,UserBlockingAboveNormalPriority %*
exit /b %ERRORLEVEL%
