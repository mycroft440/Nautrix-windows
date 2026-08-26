# Nautrix Windows

Nautrix Windows is a Windows browser focused on responsiveness and low latency.

The browser is based on the **full Chromium source tree**, not WebView2, CEF,
Electron, or another embedded webview layer.

## Current Chromium base

The downstream layer is pinned to the Windows Stable Chromium release recorded
in `chromium/VERSION`:

- Chromium `152.0.7977.65`
- revision `fc4d67f1788019a27e32511137ceccbd2fafdaaa`

Chromium source itself is not vendored into this GitHub repository. The build
scripts create a local `.chromium-work/` checkout and apply the Nautrix product
layer on top of that exact upstream revision.

## Why this architecture

A full Chromium browser gives Nautrix the open browser platform used by
Chromium-derived desktop browsers: Blink, V8, the Chromium network stack,
cookies/site storage, WebAuthn/passkeys, FedCM, multiprocess rendering, GPU
compositing, tabs, downloads, history, profiles, DevTools and extensions.

It does **not** make Nautrix Google Chrome. Private Google Chrome services such
as official Chrome Sync are not enabled or impersonated.

## Browser-local DNS optimizer

Nautrix has a native launcher and Chromium Network Service integration for DNS.

`config/dns.ini` supports:

- `mode=system`
- `mode=manual`
- `mode=automatic`

Automatic mode benchmarks real DNS queries against configured providers and
scores median latency, p95, jitter and failures. It can also resolve configured
`priority_hosts` through each candidate and measure TCP/443 connection setup to
the returned route, so trading-site path quality contributes to the selection.
The selected resolver is cached per network signature with hysteresis to avoid
unnecessary switching. When configured, the chosen resolver is used through
Chromium Secure DNS/DoH with the selected plain resolver available as fallback.

The implementation does not change the Windows DNS configuration globally.

See [`docs/DNS_AND_LATENCY.md`](docs/DNS_AND_LATENCY.md).

## Low-latency profile

`config/latency.ini` contains A/B-testable browser networking options. The first
profile exposes Chromium Happy Eyeballs V3 while retaining QUIC, DNS/browser
caches and connection pooling.

Nautrix treats DNS time, TCP/QUIC connect, TLS, RTT/jitter, first byte, rendering
and input latency as separate metrics. Future priority/trading-site tuning will
use Chromium's existing pre-resolve/preconnect facilities after the first full
runtime baseline is validated.

## Build

See [`docs/CHROMIUM_BUILD.md`](docs/CHROMIUM_BUILD.md).

Typical flow from `cmd.exe`:

```bat
tools\bootstrap_chromium.cmd
tools\build_chromium.cmd
tools\run_nautrix.cmd
```

`tools\run_nautrix.cmd` builds/uses the native `NautrixLauncher`, which selects
DNS according to `config/dns.ini` and then launches the Chromium browser.

Interactive Google account compatibility test:

```bat
tools\test_google_login.cmd
```

## Repository layout

```text
chromium/
  VERSION
  args/Release.gn

config/
  dns.ini
  latency.ini

launcher/
  CMakeLists.txt
  main.cpp

tools/
  bootstrap_chromium.cmd
  apply_nautrix.py
  build_chromium.cmd
  build_launcher.cmd
  run_nautrix.cmd
  test_google_login.cmd
  validate_nautrix.py
  validate_upstream_dns_patch.py

docs/
  ARCHITECTURE.md
  CHROMIUM_BUILD.md
  DNS_AND_LATENCY.md

PLAN.md
```

## CI

GitHub-hosted Windows CI validates the Nautrix downstream Chromium patch layer,
checks the DNS patch against the exact pinned upstream `network_service.cc`, and
compiles the native DNS/latency launcher. It does not perform the full Chromium
build because a complete upstream checkout/build requires a much larger Windows
environment.

## Status

The WebView2-to-Chromium source/build migration and the browser-local
custom/automatic DNS layer are implemented in the downstream repository.

The remaining gate is a full x64 Chromium build and interactive validation of
navigation, Google web login, extensions, DNS behavior and measured latency.
