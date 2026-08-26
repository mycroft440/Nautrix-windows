# Nautrix Windows — Development Plan

## Objective

Build a full Windows browser focused on low latency and responsiveness while
retaining normal modern-web compatibility.

## Architecture decision

- [x] C++/Chromium native Windows browser base.
- [x] WebView2 foundation superseded.
- [x] No CEF/Electron embedded-browser layer.
- [x] Chromium version pinned for reproducibility.
- [x] Nautrix product layer kept separately from the huge upstream source tree.

## Chromium foundation

- [x] Pin current Windows Stable Chromium release and git revision.
- [x] Add official depot_tools/gclient bootstrap flow.
- [x] Add GN Release x64 configuration.
- [x] Use Chromium end-user optimization level (`is_official_build=true`).
- [x] Keep Chrome branding/private browser-level Google credentials disabled.
- [x] Add Nautrix branding/product identity patch layer.
- [x] Give Nautrix its own Windows product/profile path.
- [x] Add lightweight CI validation for the downstream layer.
- [ ] Complete a full Chromium x64 build on a machine meeting upstream requirements.
- [ ] Launch and interactively validate the produced browser.

## Baseline browser functionality inherited from Chromium

The Chromium base provides the implementation for these features; each remains
pending until the first full Nautrix build is interactively verified.

- [ ] Tabs / multiple windows.
- [ ] Address bar and search.
- [ ] Downloads.
- [ ] History and bookmarks.
- [ ] Cookies and persistent sessions.
- [ ] Profiles and Incognito.
- [ ] Password/autofill facilities available in open Chromium.
- [ ] Site permissions.
- [ ] DevTools.
- [ ] Extensions support / Chrome Web Store compatibility validation.
- [ ] WebRTC / WebGL / WebGPU according to the selected Chromium build.
- [ ] PWA support.

## Google authentication compatibility

- [x] Remove embedded WebView architecture that Google explicitly restricts.
- [x] Use standalone Chromium browser architecture.
- [ ] Test `accounts.google.com` interactively.
- [ ] Test Gmail/YouTube Google account sessions.
- [ ] Test third-party "Continue with Google" OAuth/FedCM flow.
- [ ] Test 2FA and WebAuthn/passkeys.
- [ ] Verify sessions survive browser restart.

Official Chrome Sync is not an implementation target because Google restricts
the private Chrome services used by third-party Chromium-derived browsers.

## Custom and automatic DNS

- [x] Keep DNS overrides browser-local instead of modifying Windows globally.
- [x] Add native Windows DNS/latency launcher.
- [x] Add `system`, `manual` and `automatic` DNS modes.
- [x] Support custom nameservers and custom DoH template.
- [x] Benchmark real DNS queries rather than ICMP ping.
- [x] Track median, p95, jitter, timeout and failure rate.
- [x] Benchmark configured resolvers in parallel.
- [x] Cache the winner per network signature.
- [x] Re-test after active adapter/address/system-DNS changes.
- [x] Add hysteresis before switching resolver.
- [x] Patch Chromium Network Service to use `DnsConfigOverrides`.
- [x] Keep Chromium Secure DNS/DoH available for the selected resolver.
- [ ] Validate the DNS override against the first full Chromium runtime build.
- [ ] Measure the actual DoH HTTPS path through Chromium NetLog.
- [ ] Add settings UI for DNS mode/providers/metrics.
- [ ] Add end-to-end priority-host scoring so resolver selection also considers
      the route returned for important/trading sites.

## Performance / low latency

- [x] Production Chromium optimization level enabled.
- [x] Preserve Chromium browser/network/GPU/renderer process isolation.
- [x] Keep QUIC, DNS cache and connection pooling enabled by default.
- [x] Add A/B-configurable Happy Eyeballs V3 launch profile.
- [x] Keep DNS/provider benchmarks off the renderer/DOM path.
- [ ] Instrument cold and warm startup.
- [ ] Instrument input-to-browser-process latency.
- [ ] Instrument page/navigation timing.
- [ ] Instrument DNS, TCP/QUIC connect, TLS, first-byte, RTT and jitter separately.
- [ ] Profile CPU/RAM/GPU process behavior.
- [ ] Add configured priority/trading-host connection scoring.
- [ ] Add controlled pre-resolve/preconnect for priority hosts using Chromium's
      existing prediction/preconnect machinery.
- [ ] Establish a performance regression suite before aggressive tuning.
- [ ] Benchmark Chromium PGO against the validated baseline.
- [ ] Keep future latency-critical trading/API/order work outside renderer/DOM paths.

## Next objective

Get the native DNS/latency launcher green in Windows CI, then complete the first
full Chromium-based Nautrix x64 build. Runtime validation will cover normal
navigation, Google web login, custom/automatic DNS and the first latency
benchmarks before more aggressive network tuning.
