# Nautrix Windows

Nautrix Windows is a full-Chromium Windows browser focused on responsiveness and low latency.

The repository stores a small downstream product/network layer rather than vendoring Chromium's enormous source tree. `tools\bootstrap_chromium.cmd` checks out the exact revision pinned in `chromium/VERSION`, then applies the Nautrix patches.

## Current platform

- full Chromium source tree, not WebView2/CEF/Electron
- Windows x64 production baseline
- Nautrix product/profile identity
- normal Chromium tabs, storage, downloads, DevTools, extension platform and modern web stack inherited from upstream (runtime verification follows the first complete build)
- no Google Chrome branding or private Chrome Sync credentials

## Offline new-tab page

Nautrix replaces Chromium's third-party new-tab resources during bootstrap with
an embedded, offline-first Nautrix page. The layout, styles and behavior ship in
the browser binary and do not depend on a hosted home page or remote visual
assets. It includes the existing local most-visited component and a search box
with a locally persisted engine selector. Google is the first-launch default;
Bing, DuckDuckGo and Brave Search are also available. Internet access is used
only after the user submits a search or opens a site. Nautrix also routes every
standard desktop new-tab request to this local page, independent of Chromium's
browser-wide default search provider.

## Network / low latency

The native `NautrixLauncher.exe` implements browser-local DNS selection and latency preparation before starting Chromium:

- Automatic / Manual / Windows-system DNS modes
- custom DNS and custom DoH
- real A/AAAA DNS query timings
- direct DoH HTTPS-path timings
- median, p95, jitter and failure scoring
- IPv4 and IPv6 TCP/443 route scoring across the configured trading origins
- network-change-aware cache and switching hysteresis
- optional NetLog/startup tracing
- bounded persistent preconnect/keep-alive for selected origins
- QUIC/HTTP3 remains enabled by default
- HTTPS/SVCB remains enabled on the pinned Chromium revision

Packaged `config\dns.ini` and `config\latency.ini` files are immutable defaults.
On first launch they are copied to `%LOCALAPPDATA%\Nautrix\Config`, which is the
writable per-user configuration used thereafter. Metrics are written separately
under `%LOCALAPPDATA%\Nautrix`.

## Trading Mode

`config\latency.ini` supports three browser latency modes:

- `automatic` (default): detects configured trading domains and applies the aggressive policy only to them
- `normal`: preserves standard Chromium scheduling/network priorities
- `aggressive`: applies the low-latency policy to every site in the browser process

The automatic set currently includes MEXC, Binance, Bybit, OKX, Kraken, Coinbase and TradingView and is editable through `trading_sites=` / `preconnect_origins=`.

For matched sites Nautrix applies a downstream Chromium policy that:

- raises matching `URLRequest` traffic to Chromium's highest request priority
- bypasses background/intensive Blink throttling for the matched page
- keeps the page's general task queues at high priority while preserving Chromium's special highest/low queues
- protects configured trading sites from tab discard and requests foreground renderer/worker priority
- warms configured origins through Chromium's partitioned `PreconnectManager`
- keeps those preconnections alive with bounded idle/ping intervals

Manual mode switch:

```powershell
tools\set_trading_mode.ps1 -Mode automatic
tools\set_trading_mode.ps1 -Mode normal
tools\set_trading_mode.ps1 -Mode aggressive
```

The selected mode applies on the next Nautrix launch. The settings UI and mode
switch script update the per-user copy, not files beside the installed browser.

## Experimental low-latency A/B switches

The launcher supports stable per-machine A/B selection for optimizations that must be measured before being forced globally:

- Optimistic DNS for TCP plus intermediate DNS results / adaptive IPv6 fallback
- WebSocket over HTTP/3
- warm renderer reuse/pool features

Configure them in `config\latency.ini`. `off`, `on`, and `ab` are supported for the explicitly experimental switches. The default is `ab` for Optimistic DNS and WebSocket/H3 so regressions can be compared instead of assumed.

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

The bootstrap applies the Nautrix product/DNS layer, offline new-tab page,
keep-alive preconnect patch, trading priority/discard patch, and per-site
network/Blink scheduling patch to the exact pinned Chromium source tree.

See `docs/CHROMIUM_BUILD.md` for the Windows requirements. A complete Chromium build requires a much larger disk/RAM environment than standard hosted CI.

## Test installer package

After a complete baseline or PGO build, create a self-contained test package with the native Windows installer, launcher, configuration, and SHA-256/size manifest:

```powershell
tools\build_launcher.cmd
tools\package_test_installer.ps1 -Variant baseline
tools\verify_test_package.ps1 -PackageDir .\dist\Nautrix-baseline-x64-test
```

Run `Install-Nautrix-Test.cmd` from the resulting directory. It verifies the package before invoking the native installer, then places the launcher/configuration beside the installed browser and creates the supported Desktop and Start-menu launcher shortcuts. Browser/protocol registrations remain direct Chromium installer registrations; see `docs/TEST_INSTALL.md` for that limitation, SmartScreen guidance, and the native-helper size measurement.

## Diagnostics and measurements

Force a DNS retest:

```bat
tools\run_nautrix.cmd --force-dns-retest
```

Capture Chromium NetLog and startup trace for latency analysis:

```bat
tools\run_nautrix.cmd --nautrix-netlog --nautrix-trace
```

Run read-only Windows/NIC diagnostics:

```powershell
tools\windows_nic_diagnostics.ps1
```

This reports active adapters, RSS, RSC, interrupt-moderation/energy/buffer properties when exposed by the driver, and TCP global settings. It deliberately does not modify Windows or NIC settings.

Run navigation latency measurements on a built Chromium binary:

```powershell
tools\benchmark_navigation.ps1 -Browser <path-to-chrome.exe>
```

The benchmark records raw samples plus min/mean/p50/p95/p99/max summaries for normal and trading sites.

Interactive Google account compatibility test:

```bat
tools\test_google_login.cmd
```

Normal Google website authentication is a runtime compatibility goal. Official Chrome Sync is not enabled because it is a private Google Chrome service restricted for third-party Chromium-derived browsers.

## Status

The downstream Chromium integration, browser-local DNS override, DNS/DoH/IPv4/IPv6 route selector, Trading Mode source layer, persistent preconnect/keep-alive, selective Chromium network/Blink priority patches, A/B experimental feature injection, native diagnostics, tail-latency measurement tooling and lightweight exact-pin CI validation are implemented.

`PLAN.md` distinguishes source/CI-validated work from the final gates that still require a complete Chromium binary and an interactive Windows runtime. Source-layer validation does not claim that a full Chromium binary has already been built or that every optimization has already proven a latency win on real hardware.

Security reporting, licensing, third-party distribution obligations, Chromium
Stable monitoring and the release/signing/update gates are documented in
`SECURITY.md`, `THIRD_PARTY_NOTICES.md`, and `docs/RELEASE_SECURITY.md`. Signing
and automatic updates remain release blockers until their infrastructure is
implemented and tested.
