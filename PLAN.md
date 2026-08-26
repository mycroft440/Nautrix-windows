# Nautrix Windows — Development Plan

## Execution order

1. Stabilize/pin Chromium and keep lightweight CI green.
2. Finish browser-local custom/automatic DNS and network-route scoring.
3. Add IPv4/IPv6, real DoH-path measurement and diagnostics.
4. Add controlled Chromium pre-resolve/preconnect for priority sites.
5. Instrument startup/network/input/runtime performance and establish regression tests.
6. Add PGO build path and compare it against the baseline build.
7. Build the complete Chromium-derived Nautrix on a capable Windows runner.
8. Run browser/runtime compatibility tests (Google login, extensions, sessions, normal browser features).
9. Only after measurements, keep/tune optimizations that measurably reduce latency.

## Architecture

- [x] C++ / full Chromium native Windows browser base.
- [x] WebView2/CEF/Electron excluded.
- [x] Chromium Stable version/revision pinned.
- [x] Nautrix downstream product/network layer kept separately from the huge upstream source tree.
- [x] Chromium end-user optimization baseline (`is_official_build=true`).
- [x] Google Chrome branding/private browser OAuth credentials disabled.

## Browser foundation

- [x] depot_tools/gclient bootstrap flow.
- [x] GN + autoninja Windows x64 build flow.
- [x] Nautrix branding and Windows product/profile identity.
- [x] CI validates downstream layer and exact pinned upstream patch anchors.
- [ ] Full Chromium x64 build on a runner/workstation meeting upstream disk/RAM requirements.
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

## Google web authentication — runtime gates

- [x] Standalone Chromium architecture instead of embedded user-agent.
- [ ] `accounts.google.com` interactive sign-in.
- [ ] Gmail/YouTube session.
- [ ] Third-party Continue with Google OAuth/FedCM.
- [ ] 2FA and WebAuthn/passkeys.
- [ ] Session persistence after restart.

Official Chrome Sync remains outside the implementation target because Google restricts the private Chrome services used by third-party Chromium-derived browsers.

## Custom/automatic DNS

- [x] Browser-local override; does not silently modify Windows DNS.
- [x] Native Windows launcher.
- [x] `system`, `manual`, and `automatic` modes.
- [x] Custom nameservers and custom DoH endpoint.
- [x] Real DNS query benchmark instead of ICMP ping.
- [x] Median, p95, jitter, timeout/failure scoring.
- [x] Parallel provider benchmark.
- [x] Winner cache per network signature.
- [x] Retest after active adapter/address/system-DNS changes.
- [x] Hysteresis before resolver switching.
- [x] Chromium Network Service `DnsConfigOverrides` integration.
- [x] DoH/Secure DNS retained for selected resolver.
- [x] Exact pinned Chromium `network_service.cc` patch validation in CI.
- [x] Priority-host DNS-answer + TCP/443 route score.
- [x] A + AAAA queries and separate IPv4/IPv6 route measurements.
- [x] Direct DoH HTTPS-path measurement in the selector.
- [x] CSV metrics output.
- [x] Native Win32 DNS settings/benchmark application.
- [ ] Validate overrides and DoH using the first full Chromium runtime + NetLog.

## Performance / low latency

- [x] Chromium production optimization level.
- [x] Preserve browser/network/GPU/renderer process isolation.
- [x] Keep QUIC/HTTP3, DNS cache, socket pooling and GPU enabled by default.
- [x] Configurable Happy Eyeballs V3.
- [x] DNS/route benchmarking outside renderer/DOM paths.
- [x] Priority-host TCP/443 IPv4/IPv6 measurements.
- [x] NetLog capture on demand, disabled by default.
- [x] Startup trace on demand, disabled by default.
- [x] Browser process creation timing log.
- [x] Configurable non-realtime browser root process priority.
- [x] Priority preconnect configuration exported to Chromium.
- [ ] Patch Chromium preconnect manager path for Nautrix priority origins and validate against pinned upstream source.
- [ ] Add automated runtime resource profiler (CPU/RAM/process tree).
- [ ] Add headless navigation/startup regression suite.
- [ ] Add NetLog summarizer for DNS/connect/TLS/QUIC/request timings.
- [ ] Add baseline vs PGO benchmark workflow/scripts.
- [ ] Add full Chromium PGO build path.
- [ ] Validate cold/warm start, page/navigation, input-to-frame, DNS/TCP/TLS/QUIC/TTFB and CPU/RAM/GPU on actual Nautrix binary.

## Final hard gate

The final items require a complete Chromium checkout/build and interactive Windows runtime. Hosted lightweight CI cannot truthfully mark those runtime gates complete. The repository must provide an automated self-hosted build/test path so the remaining gates run as soon as a capable Windows runner is attached.
