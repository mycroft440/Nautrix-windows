# Nautrix DNS and low-latency network layer

## Modes

`config/dns.ini` supports `automatic`, `manual`, and `system` DNS. The resolver override is browser-local: Nautrix passes the selected configuration to Chromium's Network Service instead of silently modifying Windows DNS.

Automatic mode benchmarks the configured resolver endpoints in parallel and scores real DNS query latency, p95 tail latency, jitter, failures, encrypted DoH path latency, and TCP/443 connection time for priority hosts. Both A and AAAA records are sampled so IPv4 and IPv6 routes are compared.

## Trading/priority hosts

`priority_hosts` controls hosts whose resolver answers are followed by TCP/443 connection measurements. `preconnect_origins` in `config/latency.ini` controls origins kept warm through Chromium's own preconnect machinery. The default profile includes the MEXC website/API hosts, but the lists are editable.

The score deliberately does not assume the resolver with the smallest DNS RTT gives the fastest site path. A resolver can answer faster while returning a worse CDN/edge route.

## DoH

When `prefer_encrypted=1`, automatic mode also measures each provider's DoH HTTPS endpoint. Chromium receives the selected nameservers and DoH template through `DnsConfigOverrides`. If Secure DNS is unavailable in automatic mode, the chosen plain resolver remains the controlled fallback.

## Stability

The automatic winner is cached per network signature. The signature includes active adapters, addresses, and system DNS servers. A change in those values forces a fresh selection. A time-based retest and minimum-improvement hysteresis prevent needless resolver flapping.

## Diagnostics

The launcher writes:

- `%LOCALAPPDATA%\Nautrix\dns-metrics.csv`
- `%LOCALAPPDATA%\Nautrix\dns-selection.state`
- `%LOCALAPPDATA%\Nautrix\launch-metrics.log`

Use `--force-dns-retest` to ignore the cached winner. Use `--benchmark-only` to benchmark/select DNS without launching Chromium.

NetLog and startup tracing stay disabled during normal browsing. For a diagnostic launch:

```bat
tools\run_nautrix.cmd --nautrix-netlog --nautrix-trace
```

The resulting files are stored below `%LOCALAPPDATA%\Nautrix\NetLog` and `%LOCALAPPDATA%\Nautrix\Traces`.

## Settings UI

Run:

```bat
tools\network_settings.cmd
```

The native Win32 settings application exposes Automatic/Manual/System DNS, manual nameservers, custom DoH, encrypted-DNS preference, a one-click benchmark, and the latest provider metrics.

## Low-latency defaults

Nautrix preserves Chromium's QUIC/HTTP3, DNS cache, socket pooling, GPU process, Network Service, and renderer isolation. Happy Eyeballs V3 and controlled priority-origin preconnect are enabled in the Nautrix profile. The root browser process starts at `ABOVE_NORMAL_PRIORITY_CLASS`; real-time priority is intentionally not used.

Every non-default performance feature is configured separately so it can be A/B tested instead of becoming an unmeasured permanent tweak.
