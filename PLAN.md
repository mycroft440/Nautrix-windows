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
- [ ] Extensions support.
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

## Performance / low latency

- [ ] Instrument cold and warm startup.
- [ ] Instrument input-to-browser-process latency.
- [ ] Instrument page/navigation timing.
- [ ] Instrument DNS resolution time, network RTT and jitter independently.
- [ ] Profile CPU/RAM/GPU process behavior.
- [ ] Establish a performance regression suite before aggressive tuning.
- [ ] Keep future latency-critical trading/API work outside renderer/DOM paths.

## Automatic DNS optimizer

- [ ] Integrate with Chromium host resolution/network stack.
- [ ] Benchmark real DNS query latency rather than ICMP ping.
- [ ] Track median, p95, jitter, timeout and failure rate.
- [ ] Support encrypted DNS where appropriate.
- [ ] Add hysteresis before resolver changes.
- [ ] Re-test on interface/VPN/network changes.
- [ ] Avoid global Windows DNS changes by default.

## Next objective

Complete the first full Chromium-based Nautrix x64 build, then validate normal
navigation and Google web login before beginning latency tuning.
