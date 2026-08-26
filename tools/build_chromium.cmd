@echo off
setlocal EnableExtensions

for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "WORK=%ROOT%\.chromium-work"
set "DEPOT=%WORK%\depot_tools"
set "SRC=%WORK%\src"
set "OUT=%SRC%\out\Nautrix"

call "%ROOT%\tools\bootstrap_chromium.cmd"
if errorlevel 1 exit /b 1

set "PATH=%DEPOT%;%PATH%"
set "DEPOT_TOOLS_WIN_TOOLCHAIN=0"

if not exist "%OUT%" mkdir "%OUT%"
copy /Y "%ROOT%\chromium\args\Release.gn" "%OUT%\args.gn" >nul
if errorlevel 1 exit /b 1

pushd "%SRC%"
echo [Nautrix] Generating Chromium build files...
call gn gen out\Nautrix
if errorlevel 1 (
  popd
  exit /b 1
)

set "NINJA_SUMMARIZE_BUILD=1"
echo [Nautrix] Building the Chromium browser target...
call autoninja -C out\Nautrix chrome
if errorlevel 1 (
  popd
  exit /b 1
)
popd

if not exist "%OUT%\chrome.exe" (
  echo [Nautrix] Build finished but chrome.exe was not found.
  exit /b 1
)

echo [Nautrix] Build completed successfully.
echo [Nautrix] Run: tools\run_nautrix.cmd
exit /b 0
