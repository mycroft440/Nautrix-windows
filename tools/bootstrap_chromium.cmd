@echo off
setlocal EnableExtensions EnableDelayedExpansion

for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "VERSION_FILE=%ROOT%\chromium\VERSION"

if not exist "%VERSION_FILE%" (
  echo [Nautrix] Missing %VERSION_FILE%
  exit /b 1
)

for /f "usebackq tokens=1,* delims==" %%A in ("%VERSION_FILE%") do (
  if not "%%A"=="" set "%%A=%%B"
)

if not defined REVISION (
  echo [Nautrix] REVISION is missing from chromium\VERSION
  exit /b 1
)

set "WORK=%ROOT%\.chromium-work"
set "DEPOT=%WORK%\depot_tools"
set "SRC=%WORK%\src"

if not exist "%WORK%" mkdir "%WORK%"
where git >nul 2>&1
if errorlevel 1 (
  echo [Nautrix] Git for Windows is required.
  exit /b 1
)

if not exist "%DEPOT%\.git" (
  echo [Nautrix] Cloning depot_tools...
  git clone https://chromium.googlesource.com/chromium/tools/depot_tools.git "%DEPOT%"
  if errorlevel 1 exit /b 1
)

set "PATH=%DEPOT%;%PATH%"
set "DEPOT_TOOLS_WIN_TOOLCHAIN=0"
echo [Nautrix] Chromium %VERSION% revision %REVISION%
echo [Nautrix] Work tree: %WORK%

if not exist "%WORK%\.gclient" (
  echo [Nautrix] Initial Chromium checkout. This is a very large download.
  pushd "%WORK%"
  call fetch --no-history chromium
  if errorlevel 1 (
    popd
    exit /b 1
  )
  popd
)

pushd "%WORK%"
echo [Nautrix] Synchronizing the pinned Chromium revision...
call gclient sync -D --force --reset --revision src@%REVISION%
if errorlevel 1 (
  popd
  exit /b 1
)
popd

if not exist "%SRC%\chrome\BUILD.gn" (
  echo [Nautrix] Chromium source checkout is incomplete.
  exit /b 1
)

echo [Nautrix] Applying product/network layer...
python "%ROOT%\tools\apply_nautrix.py" "%SRC%"
if errorlevel 1 exit /b 1

echo [Nautrix] Applying priority-preconnect layer...
python "%ROOT%\tools\apply_preconnect.py" "%SRC%"
if errorlevel 1 exit /b 1

echo [Nautrix] Chromium source is ready.
exit /b 0
