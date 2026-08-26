@echo off
setlocal EnableExtensions
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "WORK=%ROOT%\.chromium-work"
set "DEPOT=%WORK%\depot_tools"
set "SRC=%WORK%\src"
set "OUT=%SRC%\out\NautrixPGO"

call "%ROOT%\tools\bootstrap_chromium_pgo.cmd"
if errorlevel 1 exit /b 1

set "PATH=%DEPOT%;%PATH%"
set "DEPOT_TOOLS_WIN_TOOLCHAIN=0"
set "GOOGLE_API_KEY="
set "GOOGLE_DEFAULT_CLIENT_ID="
set "GOOGLE_DEFAULT_CLIENT_SECRET="

if not exist "%OUT%" mkdir "%OUT%"
copy /Y "%ROOT%\chromium\args\ReleasePGO.gn" "%OUT%\args.gn" >nul
if errorlevel 1 exit /b 1

pushd "%SRC%"
call gn gen out\NautrixPGO
if errorlevel 1 (
  popd
  exit /b 1
)
call autoninja -C out\NautrixPGO chrome mini_installer
if errorlevel 1 (
  popd
  exit /b 1
)
popd

if not exist "%OUT%\chrome.exe" (
  echo [Nautrix] PGO build finished but chrome.exe was not found.
  exit /b 1
)
if not exist "%OUT%\mini_installer.exe" (
  echo [Nautrix] PGO build finished but mini_installer.exe was not found.
  exit /b 1
)

echo [Nautrix] PGO build completed successfully.
echo [Nautrix] Browser: %OUT%\chrome.exe
echo [Nautrix] Installer: %OUT%\mini_installer.exe
exit /b 0
