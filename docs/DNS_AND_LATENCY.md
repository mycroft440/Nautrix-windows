# Nautrix DNS and low-latency networking

## Goals

Nautrix keeps DNS selection browser-local. It does not modify the Windows DNS
configuration unless a future explicit user-facing option is added.

The networking work has two separate goals:

1. reduce avoidable DNS/connection setup delay;
2. keep latency-sensitive sites stable instead of chasing a one-off low sample.

No optimization is considered successful until it is benchmarked on the
finished Chromium binary.

## DNS modes

`config/dns.ini` supports:

- `mode=system` — use Chromium/Windows network configuration unchanged.
- `mode=manual` — use `manual_nameservers` and, when enabled, the custom DoH
  template.
- `mode=automatic` — benchmark configured providers and select a stable winner.

The native launcher passes the selected configuration through inherited process
environment variables. The Nautrix Chromium downstream layer reads those values
inside the Network Service and applies them with Chromium's
`net::DnsConfigOverrides`.

This preserves Chromium's DNS cache, connection pooling, Secure DNS machinery
and network process isolation.

## Automatic selection

The launcher sends real DNS A queries directly to every configured resolver.
ICMP ping is not used as the selection metric.

For every candidate it records:

- median query latency;
- p95 query latency;
- jitter;
- timeout/failure rate.

The score adds penalties for tail latency, jitter and failures. Providers are
benchmarked in parallel so the startup test does not scale linearly with the
number of candidates.

The selected resolver is cached under `%LOCALAPPDATA%\Nautrix`. The cache is
invalidated when the active network signature changes. The signature includes
active adapters, addresses and system DNS servers, so switching Ethernet,
Wi-Fi, VPN or addressing normally triggers a fresh selection.

`minimum_improvement_percent` adds hysteresis: an existing resolver remains in
use unless the challenger is meaningfully better. This prevents resolver
thrashing from tiny or temporary differences.

## Encrypted DNS

When `prefer_encrypted=1` and the selected provider has a DoH template, Nautrix
uses Chromium Secure DNS in automatic mode with that provider, retaining the
selected plain resolver as fallback for resilience. The initial automatic score
is currently measured with direct UDP DNS queries to the provider IPs. That
gives a reliable local resolver-latency baseline, but it is not yet a
measurement of the full HTTPS/DoH path.

After the first full Chromium runtime build, a later benchmark will use
Chromium NetLog/metrics to compare the actual encrypted resolution path before
we tune the score further.

## Trading / priority sites

A low DNS number is only one part of end-to-end site latency. A resolver can
answer quickly but return a CDN route that is worse for a specific trading
site. Therefore DNS latency, TCP/QUIC connection setup, TLS, network RTT/jitter,
server response time and rendering/input latency are tracked as separate
metrics.

`probe_domains` can include the domains that matter most to the user.

`priority_hosts` is already used by the automatic selector. For every candidate
resolver, Nautrix resolves each priority host through that resolver, extracts
the returned IPv4 addresses, measures TCP/443 connection setup and adds that
route latency/failure signal to the resolver score. This prevents a DNS from
winning solely because it answers quickly while returning a worse CDN/edge
route for an important trading site.

This TCP connect probe is intentionally not described as full end-to-end
browser latency: TLS, HTTP/2 or HTTP/3/QUIC, first byte and application/server
processing are measured separately in later runtime stages.

## Happy Eyeballs V3

`config/latency.ini` exposes `enable_happy_eyeballs_v3`.

When enabled, the launcher adds Chromium's `HappyEyeballsV3` feature. This
allows connection attempts to make use of intermediate DNS results sooner.
It remains an A/B benchmarkable switch because network topology determines
whether it improves a particular machine.

## Rules for low-latency tuning

Nautrix deliberately does not apply generic registry/network "tweaks" without
measurement.

In particular:

- do not disable QUIC by default;
- do not disable DNS/browser caches;
- do not disable connection pooling;
- do not collapse Chromium's browser/network/GPU/renderer process isolation;
- do not put future trading API/order work in a renderer or DOM path;
- prefer warm connections and preconnect for explicitly configured priority
  hosts after runtime validation;
- benchmark cold start, warm start, DNS, connect, TLS, first byte, input,
  rendering and any future trading-order dispatch separately.

## Next networking stages

1. Full Chromium x64 runtime build.
2. Validate browser-local custom DNS and Secure DNS.
3. Capture NetLog for selected providers.
4. Extend priority-host scoring from DNS + TCP/443 to TLS/QUIC/first-byte
   measurements captured from the real Chromium network stack.
5. Add controlled pre-resolve/preconnect for configured priority sites using
   Chromium's existing loading predictor/preconnect facilities.
6. Benchmark Happy Eyeballs V3 on/off.
7. Enable Chromium PGO only after a stable baseline exists.
8. Maintain performance-regression gates on Chromium upgrades.
