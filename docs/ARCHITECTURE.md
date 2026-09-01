# Nautrix Windows architecture

## Browser base

Nautrix is a downstream Windows browser built from the full Chromium source tree. It is not an application embedding WebView2, CEF, or Electron. Chromium itself is checked out under `.chromium-work`, pinned by `chromium/VERSION`, and patched by `tools/apply_nautrix.py`.

The bootstrap also applies `tools/apply_new_tab_page.py` to Chromium's
`new_tab_page_third_party` WebUI. The Nautrix HTML and TypeScript overrides are
compiled into Chromium resources, so their layout and controls remain available
offline. The selected search engine is stored in the page's local profile
storage; Google is used when no valid selection exists. Network navigation
begins only when a search is submitted or a shortcut is opened.

## Process model

Chromium's browser, Network Service, GPU, renderer and utility process separation is preserved. Latency-sensitive Nautrix code must not depend on renderer/DOM/JavaScript execution.

The native launcher performs resolver/path selection before Chromium starts, then passes browser-local network policy through environment values consumed by the patched Network Service. Windows DNS is left untouched unless the user explicitly changes it outside Nautrix.

Files shipped under `config` are read-only defaults. The launcher seeds
`%LOCALAPPDATA%\Nautrix\Config` once and both the launcher and settings UI use
that per-user location for mutable DNS and latency preferences. This keeps
installed program files immutable and prevents one user from changing another
user's browser policy.

## DNS/network path

Automatic selection measures plain DNS A/AAAA response time, p95, jitter/failures, the provider's DoH HTTPS path, and TCP/443 routes for configured priority hosts. A network signature and hysteresis avoid unnecessary switching. Chromium remains responsible for its own secure resolver, connection pools, QUIC/HTTP3, TLS, cache and isolation.

## Priority preconnect

Configured priority origins are exported as `NAUTRIX_PRECONNECT_ORIGINS`. The downstream Chromium patch connects those origins to Chromium's existing `PreconnectManager` path, so pre-resolve/preconnect uses Chromium's own security, partitioning and socket infrastructure instead of a parallel browser networking stack.

## Diagnostics

Normal browsing keeps tracing off. NetLog/startup trace can be enabled per launch. Runtime metrics belong under `%LOCALAPPDATA%\Nautrix`, separate from the repository and browser binaries.

## Build optimization

Baseline uses `is_official_build=true`, no Chrome branding, and PGO phase 0. PGO is a separate build/benchmark variant so its actual effect can be measured. Process priority is capped at configurable non-realtime classes by default; affinity and realtime priority are not hard-coded.

## Google authentication

Google website authentication is ordinary Chromium web navigation: cookies, redirects, TLS, FedCM, WebAuthn/passkeys and site storage. Private Google browser OAuth credentials are cleared during production builds, and official Chrome Sync is not part of Nautrix.
