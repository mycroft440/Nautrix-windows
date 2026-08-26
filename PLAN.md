# Nautrix Windows — Development Plan

## Execution order

1. [x] Stabilize/pin Chromium and lightweight CI.
2. [x] Implement browser-local custom/automatic DNS and route scoring.
3. [x] Add IPv4/IPv6, DoH path measurement and diagnostics.
4. [x] Connect priority origins to Chromium pre-resolve/preconnect.
5. [x] Add startup/network/process measurement tooling and regression automation.
6. [x] Add baseline + PGO build paths and comparison automation.
7. [x] Add self-hosted full Chromium build/package/runtime workflow.
8. [ ] Execute the complete Chromium build on a capable Windows runner.
9. [ ] Execute non-interactive and interactive runtime compatibility/performance gates on that binary.
10. [ ] Keep only optimizations proven beneficial by the runtime measurements.

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
- [x] Winner cache per network signature.
- [x] Retest after active adapter/address/system-DNS changes.
- [x] Switching hysteresis.
- [x] Chromium Network Service `DnsConfigOverrides` integration.
- [x] Secure DNS/DoH retained for selected resolver.
- [x] Exact pinned Chromium `network_service.cc` validation in hosted CI.
- [x] CSV metrics/state output.
- [ ] Verify actual DNS/DoH events with the complete Chromium binary's NetLog.

## Performance / low latency

- [x] Chromium production optimization level.
- [x] Preserve browser/network/GPU/renderer isolation.
- [x] Keep QUIC/HTTP3, DNS cache, socket pooling and GPU enabled by default.
- [x] Configurable Happy Eyeballs V3.
- [x] Configurable non-realtime root browser process priority.
- [x] Priority origins exported by launcher.
- [x] Priority origins patched into Chromium's existing `PreconnectManager` path.
- [x] Exact pinned preconnect source patch validation in hosted CI.
- [x] NetLog capture on demand; off during normal browsing.
- [x] Startup/input trace capture on demand; off during normal browsing.
- [x] NetLog duration summarizer for host resolution/connect/SSL/QUIC/HTTP/request events.
- [x] Startup/latency trace summarizer.
- [x] Browser process-creation timing log.
- [x] CPU/RAM/process-tree profiler.
- [x] Headless navigation regression benchmark.
- [x] Chromium NetLog priority-site probe.
- [x] Baseline-vs-PGO benchmark script/workflow.
- [x] Self-hosted runtime-regression workflow.
- [ ] Measure cold/warm startup on actual Nautrix browser.
- [ ] Measure DNS/TCP/TLS/QUIC/response-start timings on actual Nautrix browser.
- [ ] Measure CPU/RAM/GPU behavior on actual Nautrix browser.
- [ ] Capture real user-input-to-frame latency using the diagnostic trace on an interactive Windows session.
- [ ] Compare baseline vs PGO on the same hardware/network and select the winner.

## Final hard gate

All remaining unchecked items require a complete Chromium-derived browser binary and, for Google/passkey/input checks, an interactive Windows user session. The repository now contains the automated build, runtime, NetLog, trace, resource-profile and PGO-comparison paths; hosted lightweight CI cannot truthfully substitute for those runtime tests.
