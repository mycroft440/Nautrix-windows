# Nautrix Windows architecture

## Browser base

Nautrix is a downstream Windows browser built from the full Chromium source
tree. It is not an application embedding WebView2 or CEF.

The repository keeps only the Nautrix downstream layer. Chromium itself is
checked out under `.chromium-work/`, pinned by `chromium/VERSION`, and patched
by `tools/apply_nautrix.py`.

## Process model and latency

Chromium already separates the browser process, renderer processes, GPU
process, network service, and utility processes. Nautrix will preserve that
model rather than collapsing web content into the UI process.

Latency-sensitive Nautrix work must follow these rules:

1. Never put critical input/order/network code in a renderer/DOM path.
2. Keep page JavaScript and renderer stalls isolated from browser-critical work.
3. Measure before changing process priority, affinity, networking, or GPU flags.
4. Keep connections warm where a future feature legitimately benefits from it.
5. Integrate the automatic DNS optimizer at Chromium's network/host-resolver
   layer instead of changing Windows DNS globally by default.
6. Treat startup latency, input latency, DNS latency, network RTT/jitter, page
   rendering latency, and any future trading-order dispatch latency as separate
   metrics.

## Google authentication

The browser uses a standalone Chromium browser stack. Normal web authentication
is therefore handled as normal browser navigation: cookies, redirects, TLS,
JavaScript, WebAuthn/passkeys, FedCM and site storage are Chromium facilities.

This does not grant Nautrix access to private Google Chrome services. In
particular, official Chrome Sync is not part of the Nautrix product layer.

## Update model

To update Chromium:

1. Change the pinned version/revision in `chromium/VERSION`.
2. Run `tools\bootstrap_chromium.cmd`.
3. The checkout is reset to upstream and the Nautrix product layer is reapplied.
4. Run `python tools\validate_nautrix.py`.
5. Build with `tools\build_chromium.cmd`.
6. Re-run interactive browser/login and latency tests.
