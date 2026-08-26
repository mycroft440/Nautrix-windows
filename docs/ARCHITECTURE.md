# Nautrix Windows architecture

## Browser base

Nautrix is a downstream Windows browser built from the full Chromium source tree. It is not an application embedding WebView2 or CEF.

The repository keeps only the Nautrix downstream layer. Chromium itself is checked out under `.chromium-work/`, pinned by `chromium/VERSION`, and patched by `tools/apply_nautrix.py`.

## Process model and latency

Chromium separates the browser process, renderer processes, GPU process, network service, and utility processes. Nautrix preserves that model rather than putting web content and latency-critical work in one process.

Latency-sensitive Nautrix work follows these rules:

1. Never put critical input/order/network code in a renderer/DOM path.
2. Keep page JavaScript and renderer stalls isolated from browser-critical work.
3. Use `is_official_build=true` for the production/performance baseline; Chromium documents that a plain non-debug release build still keeps DCHECKs that can substantially hurt performance and memory usage.
4. Keep the first reproducible build at `chrome_pgo_phase=0`; enable PGO as a separate measured optimization once the baseline full build is validated.
5. Measure before changing process priority, affinity, networking, or GPU flags.
6. Integrate the automatic DNS optimizer at Chromium's network/host-resolver layer instead of changing Windows DNS globally by default.
7. Treat startup latency, input latency, DNS latency, network RTT/jitter, page rendering latency, and future order-dispatch latency as separate metrics.

## Google authentication

Normal Google account authentication is handled as normal web navigation: cookies, redirects, TLS, JavaScript, WebAuthn/passkeys, FedCM, and site storage are Chromium facilities.

Nautrix deliberately clears `GOOGLE_API_KEY`, `GOOGLE_DEFAULT_CLIENT_ID`, and `GOOGLE_DEFAULT_CLIENT_SECRET` during its production build and does not place private Google OAuth client credentials in GN args. This prevents a developer environment from accidentally enabling Chromium browser-level Google sign-in or private Chrome services.

This does not affect normal website login at `accounts.google.com` or third-party web OAuth flows. Those remain interactive validation gates for the first full build.

Official Chrome Sync is not part of Nautrix.

## Update model

1. Change the pinned version/revision in `chromium/VERSION`.
2. Run `tools\bootstrap_chromium.cmd`.
3. The checkout is reset to upstream and the Nautrix product layer is reapplied.
4. Run `python tools\validate_nautrix.py`.
5. Build with `tools\build_chromium.cmd`.
6. Re-run interactive browser/login and latency tests.
