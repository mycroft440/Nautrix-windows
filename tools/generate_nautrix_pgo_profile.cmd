@echo off
setlocal EnableExtensions
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "WORK=%ROOT%\.chromium-work"
set "SRC=%WORK%\src"
set "OUT=%SRC%\out\NautrixPGOTraining"

if not exist "%OUT%\chrome.exe" (
  echo [Nautrix] Missing instrumented browser. Run build_chromium_pgo_training.cmd first.
  exit /b 1
)

pushd "%SRC%"
python tools\pgo\generate_profile.py -C out\NautrixPGOTraining
if errorlevel 1 (
  popd
  exit /b 1
)
popd

if not exist "%OUT%\profile.profdata" (
  echo [Nautrix] PGO generation finished but profile.profdata was not found.
  exit /b 1
)

echo [Nautrix] Custom PGO profile generated: %OUT%\profile.profdata
echo [Nautrix] This profile must be benchmarked against Chromium's default profile before adoption.
exit /b 0
