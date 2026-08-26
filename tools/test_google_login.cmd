@echo off
setlocal EnableExtensions

for %%I in ("%~dp0..") do set "ROOT=%%~fI"
call "%ROOT%\tools\run_nautrix.cmd" "https://accounts.google.com/"
exit /b %ERRORLEVEL%
