# Installing and validating Nautrix on Windows

`NautrixSetup.exe` is the standalone native Windows installer produced from Chromium's `mini_installer` target. The installer archive itself contains the Nautrix browser, `NautrixLauncher.exe`, `NautrixNetworkSettings.exe`, and the DNS/latency configuration required by the launcher.

## Normal installation

1. Run `NautrixSetup.exe`.
2. Launch Nautrix from a shortcut created by the installer, or from Windows after selecting Nautrix as the handler/default browser.
3. Use `NautrixNetworkSettings.exe` from the installed Nautrix application directory when the network settings UI is needed.

The normal installation does not require `Install-Nautrix-Test.cmd`, loose helper executables, or a post-install copy step. The loose helper/config files in the test artifact exist only so the automated validator can compare their SHA-256 hashes with the copies installed from inside `NautrixSetup.exe`.

Chromium-created browser shortcuts are patched to target `NautrixLauncher.exe` while retaining Chromium's original shortcut arguments. Browser ProgIDs such as `NautrixHTM*` are also patched to route shell launches through `NautrixLauncher.exe` with the installed `chrome.exe` and co-located configuration supplied explicitly. This keeps DNS/trading/latency policy on normal shortcut, HTTP/HTTPS, file-association, and default-browser entry paths. Installer maintenance and uninstall commands remain on Chromium's native setup/browser paths rather than being redirected through the launcher.

Modern Windows controls the final user choice of default browser. Nautrix registers its browser capabilities and launcher-routed handlers; the installer does not silently take over the user's existing default-browser choice.

## Automated installation gate

`Install-Nautrix-Test.cmd` is a verification harness, not the installer. On a clean Windows test user it:

1. verifies the artifact manifest and SHA-256 hashes;
2. runs `NautrixSetup.exe` directly with no `installerdata` injection;
3. confirms the installer deployed the browser, launcher, network settings, and config itself;
4. compares the installed launcher/settings/config hashes with the build payload;
5. confirms native Desktop/Start-menu Nautrix shortcuts route through the launcher;
6. confirms installed `NautrixHTM*` shell commands route through the launcher and retain Chromium's single-argument shell safety path;
7. starts the installed browser through `NautrixLauncher.exe` and observes the installed `chrome.exe` process;
8. when `-UninstallAfterTest` is used, invokes the native uninstall registration and requires browser files, launcher payload, shortcuts, ProgIDs, and uninstall registration to disappear without manual cleanup.

The package is unsigned, so Windows SmartScreen may require an explicit tester decision. Signing is a distribution/reputation requirement; it is not used to mask functional installer failures during development. Nautrix's launcher configuration remains browser-local and does not silently rewrite Windows DNS, NIC, or other system network settings.

## Create and validate the package after a full Chromium build

```powershell
tools\build_launcher.cmd
tools\package_test_installer.ps1 -Variant baseline
tools\verify_test_package.ps1 -PackageDir .\dist\Nautrix-baseline-x64-test
tools\install_test_package.ps1 -PackageDir .\dist\Nautrix-baseline-x64-test -UninstallAfterTest
tools\measure_launcher_footprint.ps1
```

Use `-Variant pgo` after the corresponding PGO build. `package_test_installer.ps1` requires the matching `chrome.exe` so a stale or installer-only output cannot be packaged as a valid browser build. The install/uninstall gate refuses to run over an existing Nautrix installation because its purpose is to prove the full native lifecycle from a clean state.

Execute the relevant interactive checks in `RUNTIME_CHECKLIST.md` before approving a release build. Headless installation/runtime checks do not replace interactive validation of tabs, authentication, WebAuthn/passkeys, extensions, GPU paths, or real input-to-frame latency.

## Native helper footprint

The helpers use `/MT` so the test package has no `MSVCP` or `VCRUNTIME` dependency. In the current MSVC x64 measurement, the earlier `/MD` binaries totalled 319,488 bytes (225,280-byte launcher plus 94,208-byte settings UI); `/MT` totals 765,952 bytes (495,616 plus 270,336), an increase of 446,464 bytes. `/Gy`, `/Gw`, link-time optimization, `/OPT:REF`, and `/OPT:ICF` remain enabled to remove dead/duplicate code, but no startup, memory, or size reduction is claimed without a same-build measured comparison. Run `tools\measure_launcher_footprint.ps1` to record the current output sizes.
