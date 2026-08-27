# Nautrix Windows — Development Plan

## Execution order

1. [x] Stabilize/pin Chromium and lightweight CI.
2. [x] Implement browser-local custom/automatic DNS and route scoring.
3. [x] Add IPv4/IPv6, DoH path measurement and diagnostics.
4. [x] Connect priority origins to Chromium pre-resolve/preconnect.
5. [x] Add startup/network/process measurement tooling and regression automation.
6. [x] Add baseline + PGO build paths and comparison automation.
7. [x] Add self-hosted full Chromium build/package/runtime workflow.
8. [x] Implement source-level Trading Mode and low-latency Chromium patches.
9. [ ] Execute the complete Chromium build on a capable Windows runner.
10. [ ] Execute non-interactive and interactive runtime compatibility/performance gates on that binary.
11. [ ] Keep only experimental optimizations proven beneficial by runtime measurements.

## Architecture

- [x] C++ / full Chromium native Windows browser base.
- [x] WebView2/CEF/Electron excluded.
- [x] Chromium Stable version/revision pinned.
- [x] Nautrix downstream product/network layer separate from upstream source tree.
- [x] Chromium end-user optimization baseline (`is_official_build=true`).
- [x] Google Chrome branding/private browser OAuth credentials disabled.

## Browser foundation

- [x] depot_tools/gclient bootstrap.
- [x] GN + autoninja Windows x64 baseline build flow.
- [x] GN + autoninja Windows x64 PGO build flow.
- [x] Chromium default PGO profile checkout automation.
- [x] Browser + `mini_installer` build targets.
- [x] Nautrix branding and Windows product/profile identity.
- [x] CI validation against exact pinned upstream patch anchors.
- [x] Self-hosted full-build workflow and compact installer/tool packaging.
- [ ] Full Chromium x64 build executed on a machine meeting upstream disk/RAM requirements.
- [ ] Interactive runtime validation of the produced browser.

## Browser functionality inherited from Chromium — runtime gates

- [ ] Tabs / multiple windows.
- [ ] Address bar and search.
- [ ] Downloads.
- [ ] History and bookmarks.
- [ ] Cookies and persistent sessions.
- [ ] Profiles and Incognito.
- [ ] Password/autofill facilities available in open Chromium.
- [ ] Site permissions.
- [ ] DevTools.
- [ ] Extensions and Chrome Web Store compatibility.
- [ ] WebRTC / WebGL / WebGPU.
- [ ] PWA support.

These remain unchecked because source inheritance alone is not a runtime test.

## Google web authentication — runtime gates

- [x] Standalone Chromium architecture instead of embedded user-agent.
- [ ] `accounts.google.com` interactive sign-in.
- [ ] Gmail/YouTube session.
- [ ] Third-party Continue with Google OAuth/FedCM.
- [ ] 2FA and WebAuthn/passkeys.
- [ ] Session persistence after restart.

Official Chrome Sync remains outside the target because Google restricts the private Chrome services used by third-party Chromium-derived browsers.

## Custom/automatic DNS

- [x] Browser-local override; does not silently modify Windows DNS.
- [x] Native Windows DNS/latency launcher.
- [x] `system`, `manual`, and `automatic` modes.
- [x] Custom nameservers and custom DoH endpoint.
- [x] Native Win32 settings/benchmark application.
- [x] Real DNS queries instead of ICMP ping.
- [x] A + AAAA benchmark and IPv4/IPv6 resolver endpoints.
- [x] Median, p95, jitter, timeout/failure scoring.
- [x] Parallel provider benchmark.
- [x] Direct DoH HTTPS-path measurement.
- [x] Priority-host DNS-answer + TCP/443 IPv4/IPv6 route scoring.
- [x] Route scoring expanded across MEXC, Binance, Bybit, OKX, Kraken, Coinbase and TradingView.
- [x] Winner cache per network signature.
- [x] Retest after active adapter/address/system-DNS changes.
- [x] Switching hysteresis.
- [x] Chromium Network Service `DnsConfigOverrides` integration.
- [x] Secure DNS/DoH retained for selected resolver.
- [x] HTTPS/SVCB kept enabled on the pinned Chromium revision.
- [x] Exact pinned Chromium `network_service.cc` validation in hosted CI.
- [x] CSV metrics/state output.
- [ ] Verify actual DNS/DoH events with the complete Chromium binary's NetLog.

## Trading Mode / low latency

- [x] `automatic`, `normal`, and `aggressive` modes.
- [x] Automatic domain matching for MEXC, Binance, Bybit, OKX, Kraken, Coinbase and TradingView.
- [x] Editable trading-site/origin lists.
- [x] Manual mode switch script.
- [x] Automatic mode applies aggressive scheduling/network policy only to configured trading domains.
- [x] Normal mode preserves standard Chromium request/scheduler behavior.
- [x] Aggressive mode applies the low-latency matching policy globally.
- [x] Chromium `URLRequest` selective priority boost to `net::HIGHEST`.
- [x] Selective Blink background/intensive throttling bypass.
- [x] Selective Blink high task priority while preserving special Chromium queue priorities.
- [x] Trading-site tab discard protection.
- [x] Trading-site renderer/worker foreground-priority preference.
- [x] Priority origins exported by launcher.
- [x] Priority origins patched into Chromium's existing partitioned `PreconnectManager` path.
- [x] Bounded persistent preconnect/connection keep-alive with configurable idle and ping periods.
- [x] Configurable intent/preconnect policy hook.
- [x] QUIC/HTTP3 kept enabled by default.
- [x] Stable per-machine A/B switch for Optimistic DNS for TCP and related DNS/IPv6 fallback features.
- [x] Stable per-machine A/B switch for WebSocket over HTTP/3.
- [x] Warm-renderer preference/pool feature injection.
- [x] Exact pinned Chromium validators for trading priority, scheduler/network patch and keep-alive patch.
- [ ] Full-build compile validation of the patched Chromium translation units.
- [ ] Runtime A/B comparison before forcing experimental switches globally.

## Performance measurement / Windows diagnostics

- [x] Chromium production optimization level.
- [x] Preserve browser/network/GPU/renderer isolation.
- [x] Configurable Happy Eyeballs V3.
- [x] Configurable non-realtime root browser process priority.
- [x] NetLog capture on demand; off during normal browsing.
- [x] Startup/input trace capture on demand; off during normal browsing.
- [x] NetLog duration summarizer for host resolution/connect/SSL/QUIC/HTTP/request events.
- [x] Startup/latency trace summarizer.
- [x] Browser process-creation timing log.
- [x] CPU/RAM/process-tree profiler.
- [x] Headless navigation regression benchmark.
- [x] Navigation benchmark reports min/mean/p50/p95/p99/max.
- [x] Chromium NetLog priority-site probe.
- [x] Baseline-vs-PGO benchmark script/workflow.
- [x] Self-hosted runtime-regression workflow.
- [x] Read-only Windows/NIC diagnostics for RSS, RSC, interrupt moderation, energy/buffer properties and global TCP state.
- [x] NIC diagnostic tooling never silently modifies adapter/Windows network configuration.
- [ ] Measure cold/warm startup on actual Nautrix browser.
- [ ] Measure DNS/TCP/TLS/QUIC/response-start timings on actual Nautrix browser.
- [ ] Measure p50/p95/p99 navigation latency on actual Nautrix browser.
- [ ] Measure CPU/RAM/GPU behavior on actual Nautrix browser.
- [ ] Capture real user-input-to-frame latency using the diagnostic trace on an interactive Windows session.
- [ ] Compare baseline vs PGO on the same hardware/network and select the winner.

## Self-hosted runner bootstrap

- [x] Graphical Windows runner installer build workflow.
- [x] Embedded PowerShell setup backend with UAC elevation.
- [x] Prerequisite checks/install for Git, GitHub CLI, long paths and Visual Studio C++ Build Tools.
- [x] GitHub runner registration, Windows service start and online-status verification backend.
- [x] Fix DPI/window-layout bug that allowed the action buttons to be clipped below the visible window.
- [x] Start runner installation automatically after the elevated GUI opens, without depending on a visible button.
- [x] Corrected packaged installer compiled and passed Python, PowerShell and packaged self-tests in GitHub Actions.
- [ ] Run the corrected installer on the target Windows machine and confirm the visible log advances through authentication, registration, service start and runner-online verification.

## Final hard gate

All remaining unchecked items require a complete Chromium-derived browser binary and, for Google/passkey/input checks, an interactive Windows user session. Source/hosted CI validation proves the downstream scripts and exact pinned patch anchors; it does not substitute for compiling the entire Chromium tree or measuring the final binary on real hardware.
