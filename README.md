# Nautrix Windows

Nautrix Windows is a full-Chromium Windows browser focused on responsiveness and low latency.

The repository stores a small downstream product/network layer rather than vendoring Chromium's enormous source tree. `tools\bootstrap_chromium.cmd` checks out the exact revision pinned in `chromium/VERSION`, then applies the Nautrix patches.

## Current platform

- full Chromium source tree, not WebView2/CEF/Electron
- Windows x64 production baseline
- Nautrix product/profile identity
- normal Chromium tabs, storage, downloads, DevTools, extension platform and modern web stack inherited from upstream (runtime verification follows the first complete build)
- no Google Chrome branding or private Chrome Sync credentials

## Network / low latency

The native `NautrixLauncher.exe` implements browser-local DNS selection and latency preparation before starting Chromium:

- Automatic / Manual / Windows-system DNS modes
- custom DNS and custom DoH
- real A/AAAA DNS query timings
- direct DoH HTTPS-path timings
- median, p95, jitter and failure scoring
- IPv4 and IPv6 TCP/443 route scoring for priority hosts
- network-change-aware cache and switching hysteresis
- optional NetLog/startup tracing
- controlled priority-origin preconnect
- QUIC/HTTP3 remains enabled by default

Metrics are written under `%LOCALAPPDATA%\Nautrix`.

## Native network settings

Build the tools:

```bat
tools\build_launcher.cmd
```

Open the DNS settings/benchmark window:

```bat
tools\network_settings.cmd
```

The UI lets the user select Automatic, Manual/custom, or Windows system DNS, edit custom nameservers/DoH, prefer encrypted DNS, run the benchmark, and inspect the latest score table.

## Chromium build

```bat
tools\bootstrap_chromium.cmd
tools\build_chromium.cmd
tools\run_nautrix.cmd
```

See `docs/CHROMIUM_BUILD.md` for the Windows requirements. A complete Chromium build requires a much larger disk/RAM environment than standard hosted CI.

## Diagnostics

Force a DNS retest:

```bat
tools\run_nautrix.cmd --force-dns-retest
```

Capture Chromium NetLog and startup trace for latency analysis:

```bat
tools\run_nautrix.cmd --nautrix-netlog --nautrix-trace
```

Interactive Google account compatibility test:

```bat
tools\test_google_login.cmd
```

Normal Google website authentication is a runtime compatibility goal. Official Chrome Sync is not enabled because it is a private Google Chrome service restricted for third-party Chromium-derived browsers.

## Status

The downstream Chromium integration, browser-local DNS override, DNS/DoH/IPv4/IPv6 route selector, native network tools, and lightweight CI are implemented. `PLAN.md` distinguishes CI-validated work from the final gates that require a complete Chromium binary and interactive Windows runtime.
