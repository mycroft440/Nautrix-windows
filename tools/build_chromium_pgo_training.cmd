@echo off
setlocal EnableExtensions
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "WORK=%ROOT%\.chromium-work"
set "DEPOT=%WORK%\depot_tools"
set "SRC=%WORK%\src"
set "OUT=%SRC%\out\NautrixPGOTraining"

call "%ROOT%\tools\bootstrap_chromium.cmd"
if errorlevel 1 exit /b 1

set "PATH=%DEPOT%;%PATH%"
set "DEPOT_TOOLS_WIN_TOOLCHAIN=0"
set "GOOGLE_API_KEY="
set "GOOGLE_DEFAULT_CLIENT_ID="
set "GOOGLE_DEFAULT_CLIENT_SECRET="

if not exist "%OUT%" mkdir "%OUT%"
copy /Y "%ROOT%\chromium\args\ReleasePGOTraining.gn" "%OUT%\args.gn" >nul
if errorlevel 1 exit /b 1

pushd "%SRC%"
call gn gen out\NautrixPGOTraining
if errorlevel 1 (
  popd
  exit /b 1
)
call autoninja -C out\NautrixPGOTraining chrome
if errorlevel 1 (
  popd
  exit /b 1
)
popd

if not exist "%OUT%\chrome.exe" (
  echo [Nautrix] Instrumented PGO browser was not produced.
  exit /b 1
)

echo [Nautrix] PGO training browser ready: %OUT%\chrome.exe
exit /b 0
