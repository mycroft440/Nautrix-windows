@echo off
setlocal EnableExtensions

for %%I in ("%~dp0..") do set "ROOT=%%~fI"

rem Aggressive A/B mode for dedicated trading sessions. It prevents renderer
rem backgrounding and background timer throttling globally, which can reduce
rem delay in hidden dashboards but raises CPU/RAM/power use. Keep measurable.
call "%ROOT%\tools\run_nautrix.cmd" --enable-features=BrowserProcessAboveNormalPriority,UserBlockingAboveNormalPriority --disable-background-timer-throttling --disable-renderer-backgrounding %*
exit /b %ERRORLEVEL%
