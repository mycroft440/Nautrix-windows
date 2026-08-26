@echo off
setlocal EnableExtensions
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "WORK=%ROOT%\.chromium-work"
set "DEPOT=%WORK%\depot_tools"
set "SRC=%WORK%\src"
set "PROFILE=%SRC%\out\NautrixPGOTraining\profile.profdata"
set "OUT=%SRC%\out\NautrixPGOCustom"

call "%ROOT%\tools\bootstrap_chromium.cmd"
if errorlevel 1 exit /b 1

if not exist "%PROFILE%" (
  echo [Nautrix] Missing custom profile: %PROFILE%
  echo [Nautrix] Run build_chromium_pgo_training.cmd and generate_nautrix_pgo_profile.cmd first.
  exit /b 1
)

set "PATH=%DEPOT%;%PATH%"
set "DEPOT_TOOLS_WIN_TOOLCHAIN=0"
set "GOOGLE_API_KEY="
set "GOOGLE_DEFAULT_CLIENT_ID="
set "GOOGLE_DEFAULT_CLIENT_SECRET="

if not exist "%OUT%" mkdir "%OUT%"
> "%OUT%\args.gn" echo is_official_build = true
>> "%OUT%\args.gn" echo is_component_build = false
>> "%OUT%\args.gn" echo target_cpu = "x64"
>> "%OUT%\args.gn" echo chrome_pgo_phase = 2
>> "%OUT%\args.gn" echo enable_resource_allowlist_generation = false
>> "%OUT%\args.gn" echo symbol_level = 0
>> "%OUT%\args.gn" echo blink_symbol_level = 0
>> "%OUT%\args.gn" echo v8_symbol_level = 0
>> "%OUT%\args.gn" echo is_chrome_branded = false
>> "%OUT%\args.gn" echo pgo_data_path = "//out/NautrixPGOTraining/profile.profdata"

pushd "%SRC%"
call gn gen out\NautrixPGOCustom
if errorlevel 1 (
  popd
  exit /b 1
)
call autoninja -C out\NautrixPGOCustom chrome mini_installer
if errorlevel 1 (
  popd
  exit /b 1
)
popd

if not exist "%OUT%\chrome.exe" exit /b 1
if not exist "%OUT%\mini_installer.exe" exit /b 1

echo [Nautrix] Custom PGO build completed successfully.
echo [Nautrix] Benchmark this build against baseline and default-PGO on identical hardware/network.
exit /b 0
