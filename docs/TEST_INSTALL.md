# Installing a Nautrix test package

The test package contains Chromium's native Windows installer as `NautrixSetup.exe`, together with the Nautrix launcher and its existing configuration.

1. Extract the complete test-package directory; do not move only the setup executable.
2. Run `Install-Nautrix-Test.cmd`. It verifies the complete package before installation, runs Chromium's `NautrixSetup.exe`, deploys the launcher and existing configuration alongside the installed browser, and creates Desktop and Start-menu Nautrix shortcuts targeting the launcher.
3. Launch the browser through either of those Nautrix shortcuts or `Start-Nautrix.cmd`. All supported test shortcuts start the installed browser through `NautrixLauncher.exe` and the co-located configuration.
4. Use `NautrixNetworkSettings.exe` from the installed Nautrix application directory when the existing settings UI is needed.
5. Execute the relevant checks in `RUNTIME_CHECKLIST.md` before approving the build.

The package is intentionally test-oriented. It includes a payload SHA-256/byte-size manifest and a SHA-256 list that also covers the manifest itself. It is unsigned, so Windows SmartScreen may require an explicit tester decision. The package does not modify Windows DNS, NIC, or other network settings; it does install browser files and create the two user shortcuts described above.

The installer suppresses Chromium's native Desktop, Quick Launch, taskbar, and Start-menu shortcuts through `initial_preferences.json`, then creates only the two launcher shortcuts. Windows browser/protocol registrations remain Chromium installer registrations that target `chrome.exe`; they are not redirected through the launcher. Consequently, the test guarantee applies to the documented launcher shortcuts, not to default-browser or protocol-handler entrypoints.

## Create the package after a full Chromium build

```powershell
tools\build_launcher.cmd
tools\package_test_installer.ps1 -Variant baseline
tools\verify_test_package.ps1 -PackageDir .\dist\Nautrix-baseline-x64-test
tools\install_test_package.ps1 -PackageDir .\dist\Nautrix-baseline-x64-test -UninstallAfterTest
tools\measure_launcher_footprint.ps1
```

Use `-Variant pgo` after the corresponding PGO build. `package_test_installer.ps1` requires the matching `chrome.exe` as a guard that the installer is paired with a complete browser build. `-UninstallAfterTest` is intended for a clean test user or CI runner and proves the registered uninstall path; it refuses to touch an existing Nautrix installation.

## Native helper footprint

The helpers use `/MT` so the test package has no `MSVCP` or `VCRUNTIME` dependency. In the current MSVC x64 measurement, the earlier `/MD` binaries totalled 319,488 bytes (225,280-byte launcher plus 94,208-byte settings UI); `/MT` totals 765,952 bytes (495,616 plus 270,336), an increase of 446,464 bytes. `/Gy`, `/Gw`, link-time optimization, `/OPT:REF`, and `/OPT:ICF` remain enabled to remove dead/duplicate code, but no startup, memory, or size reduction is claimed without a same-build measured comparison. Run `tools\measure_launcher_footprint.ps1` to record the current output sizes.
