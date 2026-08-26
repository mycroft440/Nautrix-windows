@echo off
setlocal EnableExtensions
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "WORK=%ROOT%\.chromium-work"
set "DEPOT=%WORK%\depot_tools"

call "%ROOT%\tools\bootstrap_chromium.cmd"
if errorlevel 1 exit /b 1

python "%ROOT%\tools\enable_pgo_checkout.py" "%WORK%\.gclient"
if errorlevel 1 exit /b 1

set "PATH=%DEPOT%;%PATH%"
set "DEPOT_TOOLS_WIN_TOOLCHAIN=0"
pushd "%WORK%"
call gclient runhooks
if errorlevel 1 (
  popd
  exit /b 1
)
popd

echo [Nautrix] Chromium PGO profile checkout is ready.
exit /b 0
