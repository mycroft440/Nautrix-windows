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
    echo [Nautrix] Initial fetch did not complete cleanly.
    if not exist "%WORK%\.gclient" (
      popd
      exit /b 1
    )
    echo [Nautrix] Partial checkout detected; continuing with resumable gclient sync.
  )
  popd
)

if exist "%SRC%\.git" (
  git -C "%SRC%" rev-parse --verify HEAD >nul 2>&1
  if errorlevel 1 (
    echo [Nautrix] Repairing an interrupted initial Chromium checkout...
    git -C "%SRC%" show-ref --verify --quiet refs/remotes/origin/main
    if not errorlevel 1 (
      git -C "%SRC%" checkout --force --detach refs/remotes/origin/main
    )
    git -C "%SRC%" rev-parse --verify HEAD >nul 2>&1
    if errorlevel 1 (
      call :FetchPinnedRevisionWithRetry
      if errorlevel 1 exit /b 1
      git -C "%SRC%" checkout --force --detach FETCH_HEAD
    )
    if errorlevel 1 exit /b 1
  )
)

call :SyncChromiumWithRetry
if errorlevel 1 exit /b 1

if not exist "%SRC%\chrome\BUILD.gn" (
  echo [Nautrix] Chromium source checkout is incomplete.
  exit /b 1
)

echo [Nautrix] Applying product/network layer...
python "%ROOT%\tools\apply_nautrix.py" "%SRC%"
if errorlevel 1 exit /b 1

echo [Nautrix] Applying offline new-tab page...
python "%ROOT%\tools\apply_new_tab_page.py" "%SRC%"
if errorlevel 1 exit /b 1

echo [Nautrix] Applying native Windows installer/shell integration...
python "%ROOT%\tools\apply_installer_integration.py" "%SRC%"
if errorlevel 1 exit /b 1

echo [Nautrix] Applying priority-preconnect/keepalive layer...
python "%ROOT%\tools\apply_preconnect.py" "%SRC%"
if errorlevel 1 exit /b 1

echo [Nautrix] Applying per-site trading process/discard layer...
python "%ROOT%\tools\apply_trading_priority.py" "%SRC%"
if errorlevel 1 exit /b 1

echo [Nautrix] Applying per-site trading network/scheduler latency layer...
python "%ROOT%\tools\apply_trading_latency.py" "%SRC%"
if errorlevel 1 exit /b 1

echo [Nautrix] Applying intent-triggered trading spare-renderer warmup...
python "%ROOT%\tools\apply_trading_warmup.py" "%SRC%"
if errorlevel 1 exit /b 1

echo [Nautrix] Chromium source is ready.
exit /b 0

:FetchPinnedRevisionWithRetry
set /a FETCH_ATTEMPT=0
:FetchPinnedRevisionRetry
set /a FETCH_ATTEMPT+=1
echo [Nautrix] Fetching pinned Chromium revision ^(attempt !FETCH_ATTEMPT!/5^)...
git -C "%SRC%" fetch --no-tags origin %REVISION%
if not errorlevel 1 exit /b 0
if !FETCH_ATTEMPT! GEQ 5 (
  echo [Nautrix] Failed to fetch the pinned Chromium revision after 5 attempts.
  exit /b 1
)
set /a FETCH_DELAY=FETCH_ATTEMPT*10
echo [Nautrix] Transient Git fetch failure; retrying in !FETCH_DELAY! seconds...
timeout /t !FETCH_DELAY! /nobreak >nul
goto FetchPinnedRevisionRetry

:SyncChromiumWithRetry
set /a SYNC_ATTEMPT=0
:SyncChromiumRetry
set /a SYNC_ATTEMPT+=1
echo [Nautrix] Synchronizing the pinned Chromium revision ^(attempt !SYNC_ATTEMPT!/4^)...
pushd "%WORK%"
call gclient sync -D --force --reset --revision src@%REVISION%
set "SYNC_EXIT=!ERRORLEVEL!"
popd
if "!SYNC_EXIT!"=="0" exit /b 0
if !SYNC_ATTEMPT! GEQ 4 (
  echo [Nautrix] gclient sync failed after 4 attempts.
  exit /b 1
)
set /a SYNC_DELAY=SYNC_ATTEMPT*15
echo [Nautrix] Transient gclient sync failure; retrying in !SYNC_DELAY! seconds...
timeout /t !SYNC_DELAY! /nobreak >nul
goto SyncChromiumRetry
