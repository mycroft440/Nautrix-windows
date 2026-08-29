# Building Nautrix from Chromium on Windows

## Requirements

A full Chromium Windows checkout/build needs a capable x64 Windows machine, Visual Studio with Desktop C++/ATL/MFC components, NTFS storage, substantial free disk space (plan for 100+ GB), and preferably more than 16 GB RAM.

The repository intentionally keeps hosted CI lightweight; full builds are executed on a workstation or self-hosted runner.

The full-build workflow fails early unless an online runner has all four labels:
`self-hosted`, `Windows`, `X64`, and `nautrix-chromium`. This prevents a build
request from appearing healthy while it waits indefinitely for unavailable
capacity.

## Baseline build

```bat
tools\bootstrap_chromium.cmd
tools\build_chromium.cmd
```

The source tree is stored under `.chromium-work\src`, and the baseline output under `.chromium-work\src\out\Nautrix`.

Build/run native network tools:

```bat
tools\build_launcher.cmd
tools\network_settings.cmd
tools\run_nautrix.cmd
```

## Diagnostic launch

```bat
tools\run_nautrix.cmd --nautrix-netlog --nautrix-trace
```

This keeps profiling overhead out of normal browsing and writes diagnostics below `%LOCALAPPDATA%\Nautrix`.

## PGO

The baseline build intentionally uses `chrome_pgo_phase=0` so it can be compared against a separate PGO build. The PGO scripts/workflow enable Chromium's profile checkout and use a dedicated output directory; never infer a performance gain until the two builds have been measured on the same machine/network workload.

## Full runtime gates

After the first complete browser build, execute the runtime scripts and interactive checklist for:

- normal navigation/search/tabs/downloads/history/profiles
- Chrome extension platform / Chrome Web Store compatibility
- `accounts.google.com`, Gmail/YouTube, Continue with Google, 2FA/passkeys and session persistence
- automatic/manual DNS + DoH behavior in NetLog
- cold/warm startup, navigation, CPU/RAM/process behavior and network timings

The browser remains open Chromium branding (`is_chrome_branded=false`) and does not impersonate Google Chrome or enable private Chrome Sync services.
