# Nautrix Windows

Nautrix Windows is a Windows browser focused on responsiveness and low latency.

The browser is now based on the **full Chromium source tree**, not WebView2,
CEF, Electron, or another embedded webview layer.

## Current Chromium base

The downstream layer is pinned to the Windows Stable Chromium release recorded
in `chromium/VERSION`:

- Chromium `152.0.7977.65`
- revision `fc4d67f1788019a27e32511137ceccbd2fafdaaa`

Chromium source itself is not vendored into this GitHub repository. The build
scripts create a local `.chromium-work/` checkout and apply the Nautrix product
layer on top of that exact upstream revision.

## Why this architecture

A full Chromium browser gives Nautrix the same open browser platform used by
Chromium-derived desktop browsers: Blink, V8, the Chromium network stack,
cookies/site storage, WebAuthn/passkeys, FedCM, multiprocess rendering, GPU
compositing, tabs, downloads, history, profiles, DevTools and other browser
facilities.

This removes the embedded-user-agent limitation of the old WebView2 prototype.

It does **not** make Nautrix Google Chrome. Private Google Chrome services such
as official Chrome Sync are not enabled and are not impersonated.

## Build

See [`docs/CHROMIUM_BUILD.md`](docs/CHROMIUM_BUILD.md).

Typical flow from `cmd.exe`:

```bat
tools\bootstrap_chromium.cmd
tools\build_chromium.cmd
tools\run_nautrix.cmd
```

Interactive Google account compatibility test:

```bat
tools\test_google_login.cmd
```

## Repository layout

```text
chromium/
  VERSION              pinned upstream Stable version/revision
  args/Release.gn      Windows x64 production baseline

tools/
  bootstrap_chromium.cmd
  apply_nautrix.py
  build_chromium.cmd
  run_nautrix.cmd
  test_google_login.cmd
  validate_nautrix.py

docs/
  ARCHITECTURE.md
  CHROMIUM_BUILD.md

PLAN.md
```

## CI

GitHub-hosted CI validates the Nautrix patch/configuration layer. It does not
perform the full Chromium build because upstream Chromium requires a very large
Windows checkout/build environment. The full binary build is performed on a
Windows workstation or self-hosted runner that meets Chromium's requirements.

## Status

The source/build migration from WebView2 to Chromium is implemented in the
repository. The next gate is a full x64 Chromium build and interactive browser
validation, including Google web login.
